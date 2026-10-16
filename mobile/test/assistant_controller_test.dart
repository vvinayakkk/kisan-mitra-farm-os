import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:skyview_app/assistant/assistant_controller.dart';
import 'package:skyview_app/assistant/models.dart';
import 'package:skyview_app/core/api.dart';

const sid = '0123456789abcdef0123456789abcdef';
const session = SessionCapability(id: sid, token: 'secret');

final emptySession = {
  'messages': <Object>[],
  'pending': null,
  'tasks': <Object>[],
  'deleted_tasks': <Object>[],
  'artifacts': <Object>[],
  'attachments': <Object>[],
  'conversations': <Object>[],
};

String ndjson(List<Map<String, Object?>> events) => '${events.map(jsonEncode).join('\n')}\n';

/// Serves the JSON routes; [run] answers the streamed run request.
class FakeServer {
  FakeServer({this.sessionBody, this.events});

  Map<String, Object?>? sessionBody;
  Map<String, Object?>? events;
  http.Response? Function(http.Request)? override;
  final requests = <http.BaseRequest>[];
  final bodies = <String>[];

  http.Client json() => MockClient((r) async {
        requests.add(r);
        bodies.add(r.body);
        final custom = override?.call(r);
        if (custom != null) return custom;
        final path = r.url.path;
        if (path.endsWith('/catalog')) {
          return http.Response(jsonEncode({'skills': [], 'tools': [{'id': 'save_task', 'name': 'Saving', 'description': 'd', 'approval': true}]}), 200);
        }
        if (path == '/api/assistant/sessions/$sid') return http.Response(jsonEncode(sessionBody ?? emptySession), 200);
        if (path.endsWith('/events')) return http.Response(jsonEncode(events ?? {'events': []}), 200);
        return http.Response('{"detail":"not found"}', 404);
      });

  static http.Client stream(Stream<List<int>> Function(http.BaseRequest) body, {int status = 200}) =>
      MockClient.streaming((request, _) async => http.StreamedResponse(body(request), status));
}

AssistantController controller(FakeServer server, {required http.Client Function() stream, void Function()? onUnauthorized}) {
  final api = ApiClient(session: session, client: server.json(), baseUrl: 'http://test');
  api.onUnauthorized = onUnauthorized;
  return AssistantController(api, () => 'hi', () {}, streamClient: stream);
}

Future<void> settle(AssistantController c) async {
  for (var i = 0; i < 50 && (c.state.loading || c.state.running || c.state.recovering); i++) {
    await Future<void>.delayed(const Duration(milliseconds: 10));
  }
}

void main() {
  test('streams real tool activity, then shows the pending approval card', () async {
    final server = FakeServer();
    final c = controller(server, stream: () => FakeServer.stream((r) {
          expect(r.headers['Authorization'], 'Bearer secret');
          expect(r.headers['X-Assistant-Session'], sid);
          final body = jsonDecode((r as http.Request).body) as Map;
          expect(body['language'], 'hi');
          expect(body.containsKey('farmer_id'), isFalse);
          return Stream.value(utf8.encode(ndjson([
            {'type': 'run_started', 'run_id': 'a' * 32},
            {'type': 'tool_started', 'call_id': 'c1', 'tool': 'list_tasks', 'label': 'Reading your tasks'},
            {'type': 'tool_completed', 'call_id': 'c1', 'tool': 'list_tasks', 'result': {'saved': true}, 'elapsed_ms': 120},
            {'type': 'delta', 'text': 'Kal '},
            {'type': 'delta', 'text': 'paani do.'},
            {
              'type': 'approval',
              'pending': {'id': 'p1', 'kind': 'approval', 'tool': 'save_task', 'arguments': {'title': 'Irrigate', 'due_date': '2026-10-18'}},
            },
            {'type': 'done', 'status': 'waiting'},
          ])));
        }));
    await settle(c);
    // The final sync returns the server's pending card.
    server.sessionBody = {
      ...emptySession,
      'pending': {'id': 'p1', 'kind': 'approval', 'tool': 'save_task', 'arguments': {'title': 'Irrigate'}},
    };
    final seen = <AssistantState>[];
    c.addListener(seen.add, fireImmediately: false);
    await c.send('kal paani du?');
    // What the farmer saw while streaming, before the final server sync.
    final answer = seen.lastWhere((s) => s.running && s.messages.isNotEmpty).messages.last;
    expect(answer.text, 'Kal paani do.');
    expect(answer.activities.single.status, ActivityStatus.done);
    expect(answer.activities.single.outcome, 'Saved to your workspace');
    expect(answer.status, 'waiting');
    expect(c.state.pending?.kind, PendingKind.approval);
    expect(c.state.running, isFalse);
  });

  test('a stream that ends without a terminal event is an error, never a finished answer', () async {
    final c = controller(FakeServer(), stream: () => FakeServer.stream((_) => Stream.value(utf8.encode(ndjson([
          {'type': 'run_started', 'run_id': 'b' * 32},
          {'type': 'delta', 'text': 'Partial'},
        ])))));
    await settle(c);
    await c.send('hello');
    final answer = c.state.messages.last;
    expect(answer.status, 'error');
    expect(answer.error, contains('stopped before completion'));
  });

  test('a rejected session signs out instead of retrying', () async {
    var expired = false;
    final c = controller(FakeServer(),
        onUnauthorized: () => expired = true,
        stream: () => FakeServer.stream((_) => Stream.value(utf8.encode('{"detail":"This conversation key is invalid."}')), status: 401));
    await settle(c);
    await c.send('hello');
    expect(expired, isTrue);
    expect(c.state.messages.last.error, 'This conversation key is invalid.');
  });

  test('stop closes the stream and marks the turn stopped', () async {
    final events = StreamController<List<int>>();
    final c = controller(FakeServer(), stream: () => FakeServer.stream((_) => events.stream));
    await settle(c);
    final sending = c.send('long task');
    events.add(utf8.encode(ndjson([{'type': 'run_started', 'run_id': 'c' * 32}])));
    await Future<void>.delayed(const Duration(milliseconds: 20));
    c.stop();
    await events.close();
    await sending;
    expect(c.state.messages.last.status, 'stopped');
    expect(c.state.running, isFalse);
  });

  test('after a restart a working run is rebuilt from persisted events only', () async {
    final run = 'd' * 32;
    final server = FakeServer(
      sessionBody: {
        ...emptySession,
        'messages': [
          {'id': 'u1', 'role': 'user', 'content': 'check weather'},
          {'id': run, 'role': 'assistant', 'content': '', 'status': 'working', 'activities': []},
        ],
      },
      events: {
        'events': [
          {'sequence': 1, 'type': 'run_started', 'run_id': run},
          {'sequence': 2, 'type': 'tool_started', 'call_id': 'w', 'tool': 'weather_forecast', 'label': 'Reading your weather outlook'},
          {'sequence': 3, 'type': 'cancelled', 'run_id': run},
        ],
      },
    );
    final c = controller(server, stream: () => throw StateError('no run expected'));
    for (var i = 0; i < 20 && c.state.messages.isEmpty; i++) {
      await Future<void>.delayed(const Duration(milliseconds: 10));
    }
    // Recovery replays /events with the run id and then re-syncs.
    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(server.requests.any((r) => r.url.path.endsWith('/events') && r.url.queryParameters['run_id'] == run), isTrue);
    expect(c.state.recovering, isFalse);
  });

  test('undo after delete restores with the version the server bumped', () async {
    final tid = 'a' * 32;
    final server = FakeServer(sessionBody: {
      ...emptySession,
      'deleted_tasks': [
        {'id': tid, 'title': 'Scout', 'due_date': '2026-10-18', 'completed': false, 'deleted': true, 'row_version': 2},
      ],
    });
    String? ifMatch;
    server.override = (r) {
      if (!r.url.path.endsWith('/restore')) return null;
      ifMatch = r.headers['If-Match'];
      return http.Response('{}', 200);
    };
    final api = ApiClient(session: session, baseUrl: 'http://test', client: server.json());
    final c = AssistantController(api, () => 'en', () {}, streamClient: () => throw StateError('none'));
    await settle(c);
    await c.changeTask(FarmTask(id: tid, title: 'Scout', dueDate: '2026-10-18', rowVersion: 1), restore: true);
    expect(ifMatch, '2');
  });
}
