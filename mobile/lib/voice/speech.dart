import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

import '../core/api.dart';
import '../core/language.dart';
import '../core/session.dart';

/// What the server actually has configured (never assumed client-side).
class SpeechCapabilities {
  const SpeechCapabilities({
    this.transcription = false,
    this.playback = false,
    this.conversation = false,
    this.playbackLanguages = const {},
    this.maxSeconds = 30,
  });

  final bool transcription;
  final bool playback;
  final bool conversation;
  final Set<String> playbackLanguages;
  final int maxSeconds;

  factory SpeechCapabilities.fromJson(Object? v) {
    final j = v is Map ? v : const {};
    return SpeechCapabilities(
      transcription: j['transcription_available'] == true,
      playback: j['playback_available'] == true,
      conversation: j['conversation_available'] == true,
      playbackLanguages: {...(j['playback_languages'] as List? ?? const []).map((e) => '$e')},
      maxSeconds: (j['recommended_recording_seconds'] as num?)?.toInt() ?? 30,
    );
  }
}

/// Picks the speech language for an answer from its script, so a Hindi answer
/// to an English-preference farmer is still spoken in Hindi.
String speechLanguageFor(String text, String preference) {
  int count(RegExp r) => r.allMatches(text).length;
  final scripts = <String, int>{
    'deva': count(RegExp(r'[ऀ-ॿ]')),
    'bn': count(RegExp(r'[ঀ-৿]')),
    'pa': count(RegExp(r'[਀-੿]')),
    'gu': count(RegExp(r'[઀-૿]')),
    'or': count(RegExp(r'[଀-୿]')),
    'ta': count(RegExp(r'[஀-௿]')),
    'te': count(RegExp(r'[ఀ-౿]')),
    'kn': count(RegExp(r'[ಀ-೿]')),
    'ml': count(RegExp(r'[ഀ-ൿ]')),
  };
  final top = scripts.entries.reduce((a, b) => a.value >= b.value ? a : b);
  if (top.value < 3) {
    // Latin text: Hinglish reads best with the Hindi voice when Hindi is preferred.
    return speechLanguage(preference == 'hi' ? 'hi' : 'en');
  }
  if (top.key == 'deva') return speechLanguage(preference == 'mr' ? 'mr' : 'hi');
  return speechLanguage(top.key);
}

/// Markdown and links are read as plain sentences.
String speakableText(String markdown) => markdown
    .replaceAll(RegExp(r'```[\s\S]*?```'), '')
    .replaceAllMapped(RegExp(r'\[([^\]]+)\]\([^)]*\)'), (m) => m.group(1)!)
    .replaceAll(RegExp(r'[#*_`>|]'), '')
    .replaceAll(RegExp(r'\s+'), ' ')
    .trim();

class SpeechService {
  SpeechService(this._api);

  final ApiClient _api;
  final _recorder = AudioRecorder();
  final _player = AudioPlayer();
  String? _path;

  Future<SpeechCapabilities> capabilities() async =>
      SpeechCapabilities.fromJson(await _api.get('/api/speech/capabilities', timeout: const Duration(seconds: 12)));

  /// Explicit runtime permission, with a reason the farmer can read first.
  Future<bool> ensureMicrophone(BuildContext context) async {
    var status = await Permission.microphone.status;
    if (status.isGranted) return true;
    if (status.isPermanentlyDenied) {
      if (!context.mounted) return false;
      final open = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('Microphone is off'),
          content: const Text('Voice input needs microphone access. You can allow it in Settings, or keep typing.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Not now')),
            FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Open Settings')),
          ],
        ),
      );
      if (open == true) await openAppSettings();
      return false;
    }
    if (!context.mounted) return false;
    final proceed = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('Use your microphone?'),
        content: const Text(
            'Kisan Mitra records only while you speak, sends the recording to the configured speech service to '
            'turn it into text, and shows the text for you to check. The app does not keep the audio.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Not now')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('Allow microphone')),
        ],
      ),
    );
    if (proceed != true) return false;
    status = await Permission.microphone.request();
    return status.isGranted;
  }

  Stream<double> levels() => _recorder
      .onAmplitudeChanged(const Duration(milliseconds: 120))
      .map((a) => ((a.current + 50) / 50).clamp(0.0, 1.0));

  Future<void> start() async {
    final dir = await getTemporaryDirectory();
    _path = '${dir.path}/mitra-${DateTime.now().millisecondsSinceEpoch}.wav';
    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1),
      path: _path!,
    );
  }

  Future<void> cancel() async {
    await _recorder.cancel();
    await _discard();
  }

  /// Stops recording and returns the transcript for the farmer to review.
  Future<String> stopAndTranscribe(String languageCode) async {
    final path = await _recorder.stop() ?? _path;
    if (path == null) throw ApiException(400, 'Nothing was recorded. Please try again.');
    try {
      final bytes = await File(path).readAsBytes();
      if (bytes.length < 2000) throw ApiException(400, 'The recording was too short. Hold and speak again.');
      final data = await _api.multipart(
        '/api/speech/transcribe',
        http.MultipartFile.fromBytes('file', bytes, filename: 'recording.wav', contentType: MediaType('audio', 'wav')),
        fields: {'language_code': languageCode},
      );
      final text = data is Map ? data['transcript'] : null;
      if (text is! String || text.trim().isEmpty) {
        throw ApiException(503, 'No speech was transcribed. Please retry or type.');
      }
      return text.trim();
    } finally {
      await _discard();
    }
  }

  Future<void> _discard() async {
    final path = _path;
    _path = null;
    if (path != null) {
      try {
        await File(path).delete();
      } catch (_) {}
    }
  }

  /// Synthesises and plays; completes when playback ends or is stopped.
  Future<void> speak(String text, String languageCode) async {
    final data = await _api.post('/api/speech/synthesize',
        body: {'text': text.length > 2500 ? text.substring(0, 2500) : text, 'language': languageCode},
        timeout: const Duration(seconds: 30));
    final audio = data is Map ? data['audio'] : null;
    if (audio is! String || data['mime_type'] != 'audio/wav') {
      throw ApiException(503, 'Playback unavailable. Your answer is in the chat.');
    }
    final done = Completer<void>();
    _playing = done;
    final sub = _player.onPlayerComplete.listen((_) {
      if (!done.isCompleted) done.complete();
    });
    try {
      await _player.play(BytesSource(base64Decode(audio), mimeType: 'audio/wav'));
      await done.future;
    } finally {
      await sub.cancel();
      if (identical(_playing, done)) _playing = null;
    }
  }

  Completer<void>? _playing;

  Future<void> stopSpeaking() async {
    await _player.stop();
    final playing = _playing;
    if (playing != null && !playing.isCompleted) playing.complete();
  }

  void dispose() {
    _recorder.dispose();
    _player.dispose();
  }
}

final speechProvider = Provider<SpeechService>((ref) {
  final service = SpeechService(ref.watch(apiProvider));
  ref.onDispose(service.dispose);
  return service;
});

final speechCapabilitiesProvider = FutureProvider<SpeechCapabilities>(
    (ref) => ref.watch(speechProvider).capabilities());
