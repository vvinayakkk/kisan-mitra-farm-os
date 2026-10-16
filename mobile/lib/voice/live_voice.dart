import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../assistant/assistant_controller.dart';
import '../assistant/models.dart';
import '../core/api.dart';
import '../core/language.dart';
import '../ui/kit.dart';
import '../utils/constants.dart';
import 'speech.dart';

/// Turn-based live voice, matching the web: listen → transcribe → run the
/// same assistant task path → speak the answer → listen again. Questions and
/// approvals still need the on-screen card; voice never approves anything.
Future<void> openLiveVoice(BuildContext context, {RunContext runContext = const RunContext()}) async {
  final ref = ProviderScope.containerOf(context);
  SpeechCapabilities caps;
  try {
    caps = await ref.read(speechCapabilitiesProvider.future);
  } catch (_) {
    caps = const SpeechCapabilities();
  }
  if (!context.mounted) return;
  final language = speechLanguage(ref.read(languageProvider).code);
  if (!caps.conversation || !caps.playbackLanguages.contains(language)) {
    showNotice(context, 'Live voice is unavailable for this language on this server. You can still type or use voice input.');
    return;
  }
  if (!await ref.read(speechProvider).ensureMicrophone(context)) return;
  if (!context.mounted) return;
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    isDismissible: false,
    useSafeArea: true,
    builder: (_) => LiveVoiceSheet(runContext: runContext, maxSeconds: caps.maxSeconds),
  );
}

enum LivePhase { listening, understanding, working, preparing, speaking, review, muted, error }

String livePhaseLabel(LivePhase p) => switch (p) {
      LivePhase.listening => 'Listening',
      LivePhase.understanding => 'Understanding',
      LivePhase.working => 'Mitra is working',
      LivePhase.preparing => 'Preparing voice reply',
      LivePhase.speaking => 'Mitra is speaking',
      LivePhase.review => 'Review the card to continue',
      LivePhase.muted => 'Microphone off',
      LivePhase.error => 'Something went wrong',
    };

class LiveVoiceSheet extends ConsumerStatefulWidget {
  const LiveVoiceSheet({super.key, required this.runContext, required this.maxSeconds});

  final RunContext runContext;
  final int maxSeconds;

  @override
  ConsumerState<LiveVoiceSheet> createState() => _LiveVoiceSheetState();
}

class _LiveVoiceSheetState extends ConsumerState<LiveVoiceSheet> {
  LivePhase _phase = LivePhase.listening;
  String? _error;
  String _heard = '';
  double _level = 0;
  int _generation = 0;
  StreamSubscription<double>? _levels;
  Timer? _limit;
  DateTime? _lastVoice;
  bool _spoke = false;

  SpeechService get _speech => ref.read(speechProvider);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _listen());
  }

  Future<void> _listen() async {
    final turn = ++_generation;
    setState(() {
      _phase = LivePhase.listening;
      _error = null;
      _spoke = false;
      _lastVoice = null;
    });
    try {
      await _speech.start();
    } catch (_) {
      return _fail('The microphone could not start.');
    }
    _limit = Timer(Duration(seconds: widget.maxSeconds), () => _finishTurn(turn));
    _levels = _speech.levels().listen((level) {
      if (!mounted || turn != _generation) return;
      setState(() => _level = level);
      final now = DateTime.now();
      if (level > 0.35) {
        _spoke = true;
        _lastVoice = now;
      } else if (_spoke && _lastVoice != null && now.difference(_lastVoice!) > const Duration(milliseconds: 1600)) {
        _finishTurn(turn);
      }
    });
  }

  Future<void> _stopListening() async {
    _limit?.cancel();
    await _levels?.cancel();
    _levels = null;
  }

  Future<void> _finishTurn(int turn) async {
    if (turn != _generation || _phase != LivePhase.listening) return;
    await _stopListening();
    setState(() => _phase = LivePhase.understanding);
    final String text;
    try {
      text = await _speech.stopAndTranscribe(speechLanguage(ref.read(languageProvider).code));
    } on ApiException catch (e) {
      return _fail(e.message);
    }
    if (turn != _generation || !mounted) return;
    setState(() {
      _heard = text;
      _phase = LivePhase.working;
    });
    final assistant = ref.read(assistantProvider.notifier);
    await assistant.send(text, context: widget.runContext);
    if (turn != _generation || !mounted) return;
    final state = ref.read(assistantProvider);
    if (state.pending != null) {
      setState(() => _phase = LivePhase.review);
      return;
    }
    final answer = state.messages.lastWhere((m) => m.role == Role.assistant,
        orElse: () => const ChatMessage(id: '', role: Role.assistant));
    if (answer.error != null) return _fail(answer.error!);
    if (answer.text.isEmpty) return _listen();
    await _say(answer.text, turn);
  }

  Future<void> _say(String text, int turn) async {
    setState(() => _phase = LivePhase.preparing);
    try {
      final speakable = speakableText(text);
      final language = speechLanguageFor(speakable, ref.read(languageProvider).code);
      final speaking = _speech.speak(speakable, language);
      if (mounted && turn == _generation) setState(() => _phase = LivePhase.speaking);
      await speaking;
    } on ApiException catch (e) {
      return _fail(e.message);
    }
    if (mounted && turn == _generation && _phase == LivePhase.speaking) await _listen();
  }

  void _fail(String message) {
    if (!mounted) return;
    setState(() {
      _phase = LivePhase.error;
      _error = message;
    });
  }

  Future<void> _interrupt() async {
    _generation++;
    await _stopListening();
    await _speech.cancel();
    await _speech.stopSpeaking();
    ref.read(assistantProvider.notifier).stop();
  }

  Future<void> _toggleMute() async {
    if (_phase == LivePhase.muted) return _listen();
    _generation++;
    await _stopListening();
    await _speech.cancel();
    setState(() => _phase = LivePhase.muted);
  }

  Future<void> _end() async {
    await _interrupt();
    if (mounted) Navigator.pop(context);
  }

  @override
  void dispose() {
    _generation++;
    _limit?.cancel();
    _levels?.cancel();
    _speech.cancel();
    _speech.stopSpeaking();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final status = ref.watch(assistantProvider.select((s) => s.status));
    final ink = inkColor(context);
    final busy = _phase == LivePhase.working || _phase == LivePhase.speaking || _phase == LivePhase.preparing;
    return FarmBackground(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Live voice', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: ink)),
            const SizedBox(height: 28),
            AnimatedContainer(
              duration: const Duration(milliseconds: 150),
              width: 120 + (_phase == LivePhase.listening ? _level * 40 : 0),
              height: 120 + (_phase == LivePhase.listening ? _level * 40 : 0),
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(colors: [
                  AppColors.primaryLight,
                  _phase == LivePhase.speaking ? AppColors.primaryDark : AppColors.primary,
                ]),
              ),
              child: Icon(
                _phase == LivePhase.speaking ? Icons.graphic_eq : Icons.mic,
                size: 44,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 22),
            Semantics(
              liveRegion: true,
              child: Text(
                _phase == LivePhase.error
                    ? _error!
                    : _phase == LivePhase.working && status.isNotEmpty
                        ? status
                        : livePhaseLabel(_phase),
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 16, color: ink),
              ),
            ),
            if (_heard.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text('“$_heard”',
                  textAlign: TextAlign.center,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(color: mutedColor(context))),
            ],
            const SizedBox(height: 28),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              alignment: WrapAlignment.center,
              children: [
                if (_phase == LivePhase.listening)
                  FilledButton.icon(
                    onPressed: () => _finishTurn(_generation),
                    icon: const Icon(Icons.stop_rounded),
                    label: const Text('Done speaking'),
                  ),
                if (busy)
                  OutlinedButton.icon(
                    onPressed: () async {
                      await _interrupt();
                      await _listen();
                    },
                    icon: const Icon(Icons.pan_tool_alt_outlined),
                    label: const Text('Interrupt'),
                  ),
                if (_phase == LivePhase.error || _phase == LivePhase.review)
                  OutlinedButton.icon(
                    onPressed: _phase == LivePhase.review ? () => Navigator.pop(context) : _listen,
                    icon: Icon(_phase == LivePhase.review ? Icons.fact_check_outlined : Icons.refresh),
                    label: Text(_phase == LivePhase.review ? 'Open the card' : 'Resume'),
                  ),
                IconButton.outlined(
                  tooltip: _phase == LivePhase.muted ? 'Unmute microphone' : 'Mute microphone',
                  onPressed: busy ? null : _toggleMute,
                  icon: Icon(_phase == LivePhase.muted ? Icons.mic_off : Icons.mic),
                ),
                IconButton.filled(
                  tooltip: 'End live conversation',
                  style: IconButton.styleFrom(backgroundColor: AppColors.error),
                  onPressed: _end,
                  icon: const Icon(Icons.close),
                ),
              ],
            ),
            const SizedBox(height: 16),
            Text('Audio goes to the configured speech service. Reviews and approvals stay on screen.',
                textAlign: TextAlign.center, style: TextStyle(fontSize: 11, color: mutedColor(context))),
          ],
        ),
      ),
    );
  }
}
