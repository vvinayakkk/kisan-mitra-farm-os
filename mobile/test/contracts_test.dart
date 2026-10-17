import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:skyview_app/assistant/models.dart';
import 'package:skyview_app/assistant/run_events.dart';
import 'package:skyview_app/assistant/suggestions.dart';
import 'package:skyview_app/core/api.dart';
import 'package:skyview_app/core/ids.dart';
import 'package:skyview_app/core/language.dart';
import 'package:skyview_app/core/read_cache.dart';
import 'package:skyview_app/ui/provenance.dart';
import 'package:skyview_app/voice/speech.dart';

import 'l10n.dart';

void main() {
  setUpAll(loadEnglish);

  group('session capability', () {
    test('accepts only server-shaped ids', () {
      expect(SessionCapability.tryParse({'id': 'a' * 32, 'token': 't'}), isNotNull);
      expect(SessionCapability.tryParse({'session_id': 'b' * 32, 'token': 't'})?.id, 'b' * 32);
      expect(SessionCapability.tryParse({'id': 'farmer-1', 'token': 't'}), isNull);
      expect(SessionCapability.tryParse({'id': 'a' * 32, 'token': ''}), isNull);
    });
  });

  group('api errors', () {
    test('surfaces FastAPI string and validation details', () async {
      final api = ApiClient(
        baseUrl: 'http://t',
        client: MockClient((r) async => r.url.path == '/a'
            ? http.Response('{"detail":"Task changed"}', 409)
            : http.Response('{"detail":[{"msg":"Field required"}]}', 422)),
      );
      await expectLater(api.get('/a'), throwsA(isA<ApiException>().having((e) => e.conflict, 'conflict', isTrue)));
      await expectLater(api.get('/b'), throwsA(isA<ApiException>().having((e) => e.message, 'message', 'Please check the details you entered.')));
    });

    test('network failure is reported as offline, not as an empty result', () async {
      final api = ApiClient(baseUrl: 'http://t', client: MockClient((_) => throw http.ClientException('down')));
      await expectLater(api.get('/x'), throwsA(isA<ApiException>().having((e) => e.offline, 'offline', isTrue)));
    });
  });

  group('run events', () {
    test('malformed stream lines fail loudly', () async {
      final stream = ndjsonEvents(Stream.value(utf8.encode('{"type":"delta","text":"a"}\nnot json\n')));
      await expectLater(stream.toList(), throwsA(isA<FormatException>()));
    });

    test('failed tools keep their error and never become results', () {
      var m = const ChatMessage(id: 'x', role: Role.assistant, status: 'working');
      m = foldEvent(m, {'type': 'tool_started', 'call_id': '1', 'tool': 'market_prices', 'label': 'Checking mandi prices'}).message;
      final f = foldEvent(m, {'type': 'tool_failed', 'call_id': '1', 'error': 'Source unavailable'});
      expect(f.message.activities.single.status, ActivityStatus.error);
      expect(f.message.activities.single.outcome, 'Source unavailable');
      expect(f.artifact, isNull);
    });

    test('duplicate tool_started (replay overlap) does not duplicate rows', () {
      var m = const ChatMessage(id: 'x', role: Role.assistant);
      final e = {'type': 'tool_started', 'call_id': '1', 'tool': 't', 'label': 'L'};
      m = foldEvent(foldEvent(m, e).message, e).message;
      expect(m.activities, hasLength(1));
    });

    test('unavailable data is labelled, not shown as success', () {
      const a = Activity(callId: '1', tool: 'weather_forecast', label: 'L', status: ActivityStatus.done, result: {'available': false});
      expect(a.outcome, 'Data unavailable — no values assumed');
    });
  });

  group('models', () {
    test('structured answers read as farmer text', () {
      expect(readableHistory('Requested details: {"farmer_answers":{"crop_name":"Wheat","acres":"2"}}'),
          'crop name: Wheat · acres: 2');
      expect(readableHistory('Calendar context: selected date 2026-10-17. Farmer request: Plan'), 'Plan');
    });

    test('question card exposes one field at a time with clean prompts', () {
      final p = Pending.fromJson({
        'id': 'q',
        'kind': 'question',
        'tool': 'ask_farmer',
        'arguments': {
          'question': 'A little more detail',
          'fields': [
            {'id': 'crop', 'label': 'Crop (e.g., wheat)', 'type': 'select', 'options': ['Wheat', 'Rice']},
            {'id': 'photo', 'label': 'Leaf photo', 'type': 'photo'},
          ],
        },
      })!;
      expect(p.fields.first.prompt, 'Crop');
      expect(p.fields.last.type, 'photo');
    });

    test('task patch carries the row version for conflict detection', () {
      final t = FarmTask.fromJson({'id': 'a' * 32, 'title': 'Scout', 'due_date': '2026-10-17', 'row_version': 3});
      expect(t.copyWith(completed: true).toPatch()['row_version'], 3);
    });
  });

  group('read cache', () {
    test('expires, stays bounded and drops loads started before invalidation', () async {
      var now = DateTime(2026);
      var loads = 0;
      final cache = ReadCache(maxEntries: 2, ttl: const Duration(minutes: 1));
      Future<int> load() async => ++loads;
      await cache.read('a', load, now: () => now);
      await cache.read('a', load, now: () => now);
      expect(loads, 1);
      now = now.add(const Duration(minutes: 2));
      await cache.read('a', load, now: () => now);
      expect(loads, 2);
      await cache.read('b', load, now: () => now);
      await cache.read('c', load, now: () => now);
      expect(cache.length, 2);

      final slow = cache.read('d', () async {
        await Future<void>.delayed(const Duration(milliseconds: 10));
        return 99;
      });
      cache.invalidate();
      expect(await slow, 99);
      expect(cache.length, 0);
    });
  });

  group('language and speech', () {
    test('normalises the backend language codes', () {
      expect(normalizeLanguage('od-IN'), 'or');
      expect(normalizeLanguage('xx'), isNull);
      expect(speechLanguage('or'), 'od-IN');
    });

    test('answers are spoken in their own script', () {
      expect(speechLanguageFor('कल सिंचाई करें', 'en'), 'hi-IN');
      expect(speechLanguageFor('நாளை நீர் பாய்ச்சவும்', 'en'), 'ta-IN');
      expect(speechLanguageFor('kal paani dena', 'hi'), 'hi-IN');
      expect(speechLanguageFor('Water tomorrow', 'en'), 'en-IN');
    });

    test('markdown is read as sentences', () {
      expect(speakableText('**Rain** on [IMD](https://imd.gov.in)\n# Plan'), 'Rain on IMD Plan');
    });
  });

  test('notebook helpers map to accepted run views', () {
    expect(runView('ledger'), 'records');
    expect(runView('weather'), 'weather');
    for (final key in kSuggestions.keys) {
      expect(kSuggestions[key], hasLength(4), reason: key);
    }
  });

  test('provenance never labels a forecast as observed', () {
    expect(provenanceLabel('forecast'), 'Forecast');
    expect(provenanceLabel('synthetic'), 'Sample');
    expect(provenanceLabel(null), 'Source not supplied');
  });

  test('idempotency keys are reused until success', () {
    final keys = IdempotencyKeys();
    final first = keys.forOperation('t:hello');
    expect(keys.forOperation('t:hello'), first);
    keys.succeeded('t:hello');
    expect(keys.forOperation('t:hello'), isNot(first));
    expect(RegExp(r'^[0-9a-f-]{36}$').hasMatch(first), isTrue);
  });
}
