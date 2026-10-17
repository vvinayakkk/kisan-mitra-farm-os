import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:skyview_app/assistant/assistant_controller.dart';
import 'package:skyview_app/core/api.dart';
import 'package:skyview_app/core/offline.dart';

import 'l10n.dart';

const sid = '0123456789abcdef0123456789abcdef';
const session = SessionCapability(id: sid, token: 't');

void main() {
  setUpAll(loadEnglish);
  late Directory tmp;
  setUp(() => tmp = Directory.systemTemp.createTempSync('offline'));
  tearDown(() => tmp.deleteSync(recursive: true));

  OfflineStore store({int max = 80}) => OfflineStore(sid, root: () async => tmp, maxEntries: max);

  test('serves the last saved copy only when the network fails, with its time', () async {
    var online = true;
    final s = store();
    final api = ApiClient(
      session: session,
      baseUrl: 'http://t',
      offline: s,
      client: MockClient((r) async {
        if (!online) throw http.ClientException('no network');
        return http.Response(jsonEncode({'temp': 30}), 200);
      }),
    );
    expect(await api.get('/api/weather/dashboard'), {'temp': 30});
    await Future<void>.delayed(const Duration(milliseconds: 20));
    expect(s.servedSavedAt.value, isNull);

    online = false;
    expect(await api.get('/api/weather/dashboard'), {'temp': 30});
    expect(s.servedSavedAt.value, isNotNull);

    // Never cached: writes, uncached paths, and anything not saved before.
    await expectLater(api.get('/api/speech/capabilities'), throwsA(isA<ApiException>()));
    await expectLater(api.get('/api/farm-workspace/ledger'), throwsA(isA<ApiException>()));
  });

  test('server refusals are shown, not hidden behind an old copy', () async {
    var status = 200;
    final api = ApiClient(
      session: session,
      baseUrl: 'http://t',
      offline: store(),
      client: MockClient((r) async => http.Response(status == 200 ? '{"a":1}' : '{"detail":"Invalid"}', status)),
    );
    await api.get('/api/profile');
    await Future<void>.delayed(const Duration(milliseconds: 20));
    status = 401;
    await expectLater(api.get('/api/profile'), throwsA(isA<ApiException>().having((e) => e.unauthorized, 'unauthorized', isTrue)));
  });

  test('stays bounded and is erased on sign-out', () async {
    final s = store(max: 3);
    for (var i = 0; i < 6; i++) {
      await s.save('k$i', i);
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }
    expect(Directory('${tmp.path}/offline/$sid').listSync(), hasLength(3));
    await OfflineStore.clearAll(root: () async => tmp);
    expect(Directory('${tmp.path}/offline').existsSync(), isFalse);
  });

  test('messages typed offline are kept and sent in order when signal returns', () async {
    SharedPreferences.setMockInitialValues({});
    final sent = <String>[];
    final api = ApiClient(
      session: session,
      baseUrl: 'http://t',
      client: MockClient((r) async => r.url.path.endsWith('/catalog')
          ? http.Response('{"skills":[],"tools":[]}', 200)
          : http.Response(jsonEncode({'messages': [], 'pending': null}), 200)),
    );
    final c = AssistantController(api, () => 'hi', () {},
        streamClient: () => MockClient.streaming((request, _) async {
              sent.add(jsonDecode((request as http.Request).body)['message'] as String);
              return http.StreamedResponse(
                  Stream.value(utf8.encode('${jsonEncode({'type': 'done', 'status': 'completed'})}\n')), 200);
            }),
        isOnline: () => false);
    for (var i = 0; i < 20 && !c.state.ready; i++) {
      await Future<void>.delayed(const Duration(milliseconds: 10));
    }
    await c.queue('kal mandi bhav?');
    await c.queue('baarish hogi?');
    expect(sent, isEmpty);
    expect((await SharedPreferences.getInstance()).getStringList('outbox_$sid'), hasLength(2));

    await c.flushOutbox();
    expect(sent, ['kal mandi bhav?', 'baarish hogi?']);
    expect(c.state.outbox, isEmpty);
  });
}
