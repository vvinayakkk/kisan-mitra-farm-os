import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:skyview_app/core/api.dart';
import 'package:skyview_app/voice/speech.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test('WAV playback uses a local file and emits captions after resume', () async {
    final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    final dir = await Directory.systemTemp.createTemp('mitra-audio-test-');
    const codec = StandardMethodCodec();
    final order = <String>[];
    final paths = <String>[];
    Future<void> event(String id, String name, [Object? value]) => messenger.handlePlatformMessage(
      'xyz.luan/audioplayers/events/$id', codec.encodeSuccessEnvelope({'event': name, 'value': value}), (_) {});
    messenger.setMockMethodCallHandler(const MethodChannel('plugins.flutter.io/path_provider'), (_) async => dir.path);
    messenger.setMockMethodCallHandler(const MethodChannel('xyz.luan/audioplayers.global'), (_) async => 1);
    messenger.setMockMethodCallHandler(const MethodChannel('xyz.luan/audioplayers.global/events'), (_) async => null);
    messenger.setMockMethodCallHandler(const MethodChannel('xyz.luan/audioplayers'), (call) async {
      final args = call.arguments as Map;
      final id = args['playerId'] as String;
      if (call.method == 'create') {
        messenger.setMockMethodCallHandler(MethodChannel('xyz.luan/audioplayers/events/$id'), (_) async => null);
      }
      if (call.method == 'setSourceUrl') {
        expect(args['isLocal'], isTrue);
        final path = args['url'] as String;
        expect(File(path).existsSync(), isTrue);
        paths.add(path);
        scheduleMicrotask(() => event(id, 'audio.onPrepared', true));
      }
      if (call.method == 'resume') {
        order.add('resume');
        Future<void>.delayed(const Duration(milliseconds: 10), () => event(id, 'audio.onComplete'));
      }
      return 1;
    });
    final api = ApiClient(baseUrl: 'http://fixture', client: MockClient((r) async {
      expect(r.url.path, '/api/speech/synthesize');
      return http.Response(jsonEncode({'mime_type': 'audio/wav', 'audio': base64Encode(utf8.encode('RIFF0000WAVEfixture'))}), 200);
    }));
    final service = SpeechService(api);
    await service.speak('Your farm plan is ready.', 'en-IN', onCaption: (caption) {
      expect(order.last, 'resume');
      order.add(caption);
    });
    expect(order, ['resume', 'Your farm plan is ready.']);
    expect(paths, hasLength(1));
    expect(File(paths.single).existsSync(), isFalse);
    service.dispose();
    await Future<void>.delayed(const Duration(milliseconds: 30));
    api.close();
    await dir.delete(recursive: true);
  }, timeout: const Timeout(Duration(seconds: 10)));
}
