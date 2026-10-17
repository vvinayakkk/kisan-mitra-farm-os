import 'dart:async';

import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/api.dart';
import '../core/language.dart';
import '../ui/kit.dart';
import '../utils/constants.dart';
import 'speech.dart';

/// Tap to speak, tap again to finish. The transcript is handed back for the
/// farmer to review/edit; it is never sent automatically.
class VoiceButton extends ConsumerStatefulWidget {
  const VoiceButton({super.key, required this.onTranscript, this.enabled = true, this.size = 44});

  final void Function(String text) onTranscript;
  final bool enabled;
  final double size;

  @override
  ConsumerState<VoiceButton> createState() => _VoiceButtonState();
}

enum _Phase { idle, recording, transcribing }

class _VoiceButtonState extends ConsumerState<VoiceButton> {
  _Phase _phase = _Phase.idle;
  Timer? _limit;
  StreamSubscription<double>? _levels;
  double _level = 0;

  Future<void> _toggle() async {
    final speech = ref.read(speechProvider);
    if (_phase == _Phase.recording) return _finish();
    if (_phase != _Phase.idle) return;
    final caps = await ref.read(speechCapabilitiesProvider.future).catchError((_) => const SpeechCapabilities());
    if (!mounted) return;
    if (!caps.transcription) {
      showNotice(context, 'fos.assistant.voice_not_configured'.tr());
      return;
    }
    if (!await speech.ensureMicrophone(context)) return;
    try {
      await speech.start();
      _levels = speech.levels().listen((l) => setState(() => _level = l));
      _limit = Timer(Duration(seconds: caps.maxSeconds), _finish);
      setState(() => _phase = _Phase.recording);
    } catch (_) {
      if (mounted) showNotice(context, 'fos.assistant.mic_failed'.tr());
    }
  }

  Future<void> _finish() async {
    if (_phase != _Phase.recording) return;
    _limit?.cancel();
    await _levels?.cancel();
    setState(() => _phase = _Phase.transcribing);
    try {
      final text = await ref
          .read(speechProvider)
          .stopAndTranscribe(speechLanguage(ref.read(languageProvider).code));
      widget.onTranscript(text);
    } on ApiException catch (e) {
      if (mounted) showNotice(context, e.message);
    } finally {
      if (mounted) setState(() => _phase = _Phase.idle);
    }
  }

  @override
  void dispose() {
    _limit?.cancel();
    _levels?.cancel();
    if (_phase == _Phase.recording) ref.read(speechProvider).cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final recording = _phase == _Phase.recording;
    final label = switch (_phase) {
      _Phase.idle => 'fos.assistant.speak_instead'.tr(),
      _Phase.recording => 'fos.assistant.done_speaking'.tr(),
      _Phase.transcribing => 'fos.assistant.understanding_words'.tr(),
    };
    return Semantics(
      button: true,
      label: label,
      child: Tooltip(
        message: label,
        child: SizedBox(
          width: widget.size,
          height: widget.size,
          child: _phase == _Phase.transcribing
              ? const Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator(strokeWidth: 2))
              : AnimatedContainer(
                  duration: const Duration(milliseconds: 120),
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: recording ? AppColors.error.withValues(alpha: 0.15 + _level * 0.35) : null,
                  ),
                  child: IconButton(
                    onPressed: widget.enabled || recording ? _toggle : null,
                    icon: Icon(recording ? Icons.stop_rounded : Icons.mic_none_rounded,
                        color: recording ? AppColors.error : (context.isDark ? AppColors.primaryLight : AppColors.primaryDark)),
                  ),
                ),
        ),
      ),
    );
  }
}
