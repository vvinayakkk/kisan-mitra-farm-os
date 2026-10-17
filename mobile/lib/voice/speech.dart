import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:easy_localization/easy_localization.dart';
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
      playbackLanguages: {
        ...(j['playback_languages'] as List? ?? const []).map((e) => '$e')
      },
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
  if (top.key == 'deva') {
    return speechLanguage(preference == 'mr' ? 'mr' : 'hi');
  }
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
  AudioRecorder? _recordInstance;
  AudioPlayer? _playerInstance;
  AudioRecorder get _recorder => _recordInstance ??= AudioRecorder();
  AudioPlayer get _player => _playerInstance ??= AudioPlayer();
  String? _path;

  Future<SpeechCapabilities> capabilities() async =>
      SpeechCapabilities.fromJson(await _api.get('/api/speech/capabilities',
          timeout: const Duration(seconds: 12)));

  /// Explicit runtime permission, with a reason the farmer can read first.
  Future<bool> ensureMicrophone(BuildContext context) async {
    var status = await Permission.microphone.status;
    if (status.isGranted) return true;
    if (status.isPermanentlyDenied) {
      if (!context.mounted) return false;
      final open = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: Text('fos.assistant.mic_off_title'.tr()),
          content: Text('fos.assistant.mic_off_body'.tr()),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(c, false),
                child: Text('fos.assistant.not_now'.tr())),
            FilledButton(
                onPressed: () => Navigator.pop(c, true),
                child: Text('fos.assistant.open_settings'.tr())),
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
        title: Text('fos.assistant.mic_ask_title'.tr()),
        content: Text('fos.assistant.mic_ask_body'.tr()),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: Text('fos.assistant.not_now'.tr())),
          FilledButton(
              onPressed: () => Navigator.pop(c, true),
              child: Text('fos.assistant.allow_mic'.tr())),
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
      const RecordConfig(
          encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1),
      path: _path!,
    );
  }

  Future<void> cancel() async {
    await _recordInstance?.cancel();
    await _discard();
  }

  /// Stops recording and returns the transcript for the farmer to review.
  Future<String> stopAndTranscribe(String languageCode) async {
    final path = await _recorder.stop() ?? _path;
    if (path == null) {
      throw ApiException(400, 'fos.assistant.nothing_recorded'.tr());
    }
    try {
      final bytes = await File(path).readAsBytes();
      if (bytes.length < 2000) {
        throw ApiException(400, 'fos.assistant.recording_short'.tr());
      }
      final data = await _api.multipart(
        '/api/speech/transcribe',
        http.MultipartFile.fromBytes('file', bytes,
            filename: 'recording.wav', contentType: MediaType('audio', 'wav')),
        fields: {'language_code': languageCode},
      );
      final text = data is Map ? data['transcript'] : null;
      if (text is! String || text.trim().isEmpty) {
        throw ApiException(503, 'fos.assistant.no_speech'.tr());
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

  int _playGeneration = 0;

  /// Short sentence chunks reduce time to first audio. Captions advance only
  /// when the corresponding chunk actually begins playing.
  Future<void> speak(String text, String languageCode,
      {void Function(String)? onCaption}) async {
    final generation = ++_playGeneration;
    final chunks = speechChunks(text);
    for (final chunk in chunks) {
      if (generation != _playGeneration) return;
      final data = await _api.post('/api/speech/synthesize',
          body: {'text': chunk, 'language': languageCode},
          timeout: const Duration(seconds: 30));
      if (generation != _playGeneration) return;
      final audio = data is Map ? data['audio'] : null;
      if (audio is! String || data['mime_type'] != 'audio/wav') {
        throw ApiException(503, 'fos.assistant.playback_unavailable'.tr());
      }
      final bytes = base64Decode(audio);
      final dir = await getTemporaryDirectory();
      final file = File('${dir.path}/mitra-play-$generation.wav');
      await file.writeAsBytes(bytes, flush: true);
      if (generation != _playGeneration) {
        await file.delete();
        return;
      }
      final done = Completer<void>();
      _playing = done;
      final sub = _player.onPlayerComplete.listen((_) {
        if (!done.isCompleted) done.complete();
      });
      try {
        await _player.play(DeviceFileSource(file.path));
        onCaption?.call(chunk);
        await done.future.timeout(const Duration(minutes: 2));
      } finally {
        await sub.cancel();
        if (identical(_playing, done)) _playing = null;
        if (await file.exists()) await file.delete();
      }
    }
  }

  Completer<void>? _playing;

  Future<void> stopSpeaking() async {
    _playGeneration++;
    await _playerInstance?.stop();
    final playing = _playing;
    if (playing != null && !playing.isCompleted) playing.complete();
  }

  void dispose() {
    _playGeneration++;
    _recordInstance?.dispose();
    _playerInstance?.dispose();
    final playing = _playing;
    if (playing != null && !playing.isCompleted) playing.complete();
  }
}

final speechProvider = Provider<SpeechService>((ref) {
  final service = SpeechService(ref.watch(apiProvider));
  ref.onDispose(service.dispose);
  return service;
});

final speechCapabilitiesProvider = FutureProvider<SpeechCapabilities>(
    (ref) => ref.watch(speechProvider).capabilities());

/// Keep natural sentences together while respecting provider input limits.
List<String> speechChunks(String text, {int limit = 320}) {
  final clean = speakableText(text);
  final chunks = <String>[];
  var remaining = clean;
  while (remaining.isNotEmpty) {
    if (remaining.length <= limit) {
      chunks.add(remaining);
      break;
    }
    final window = remaining.substring(0, limit);
    final ends = RegExp(r'[.!?।]\s').allMatches(window).toList();
    var split = ends.isNotEmpty ? ends.last.end : window.lastIndexOf(' ');
    if (split < 1) split = limit;
    chunks.add(remaining.substring(0, split).trim());
    remaining = remaining.substring(split).trim();
  }
  return chunks;
}
