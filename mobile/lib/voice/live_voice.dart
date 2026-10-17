import 'dart:async';

import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:speech_to_text/speech_to_text.dart';
import '../assistant/widgets/pending_card.dart';
import '../ui/mitra_orb.dart';
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
Future<void> openLiveVoice(BuildContext context,
    {RunContext runContext = const RunContext()}) async {
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
    showNotice(context, 'fos.assistant.live_unavailable'.tr());
    return;
  }
  if (!await ref.read(speechProvider).ensureMicrophone(context)) return;
  if (!context.mounted) return;
  await Navigator.of(context).push<void>(MaterialPageRoute(
    fullscreenDialog: true,
    builder: (_) =>
        LiveVoiceSheet(runContext: runContext, maxSeconds: caps.maxSeconds),
  ));
}

enum LivePhase {
  listening,
  understanding,
  working,
  preparing,
  speaking,
  review,
  muted,
  error
}

String livePhaseLabel(LivePhase p) => switch (p) {
      LivePhase.listening => 'fos.assistant.phase_listening'.tr(),
      LivePhase.understanding => 'fos.assistant.phase_understanding'.tr(),
      LivePhase.working => 'fos.assistant.phase_working'.tr(),
      LivePhase.preparing => 'fos.assistant.phase_preparing'.tr(),
      LivePhase.speaking => 'fos.assistant.phase_speaking'.tr(),
      LivePhase.review => 'fos.assistant.phase_review'.tr(),
      LivePhase.muted => 'fos.assistant.phase_muted'.tr(),
      LivePhase.error => 'fos.assistant.phase_error'.tr(),
    };

class LiveVoiceSheet extends ConsumerStatefulWidget {
  const LiveVoiceSheet(
      {super.key, required this.runContext, required this.maxSeconds});

  final RunContext runContext;
  final int maxSeconds;

  @override
  ConsumerState<LiveVoiceSheet> createState() => _LiveVoiceSheetState();
}

class _LiveVoiceSheetState extends ConsumerState<LiveVoiceSheet>
    with WidgetsBindingObserver {
  LivePhase _phase = LivePhase.listening;
  String? _error;
  String _heard = '';
  double _level = 0;
  int _generation = 0;
  StreamSubscription<double>? _levels;
  Timer? _limit;
  DateTime? _lastVoice;
  bool _spoke = false;
  final _recognizer = SpeechToText();
  bool _native = false;
  bool _useRecording = false;
  String _caption = '';
  int _queuedChars = 0;
  Future<void> _speechQueue = Future.value();
  String? _playbackError;
  final _started = DateTime.now();
  Timer? _clock;
  late SpeechService _service;
  late AssistantController _assistant;
  ProviderSubscription<AssistantState>? _assistantListener;

  SpeechService get _speech => _service;

  @override
  void initState() {
    super.initState();
    _service = ref.read(speechProvider);
    _assistant = ref.read(assistantProvider.notifier);
    WidgetsBinding.instance.addObserver(this);
    _clock = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
    _assistantListener = ref.listenManual(assistantProvider, (previous, next) {
      if (next.running &&
          {LivePhase.working, LivePhase.preparing, LivePhase.speaking}
              .contains(_phase)) {
        final answer = next.messages.lastOrNull;
        if (answer?.role == Role.assistant) {
          _queueAnswer(answer!.text, _generation);
        }
      }
      if (_phase == LivePhase.review && previous?.busy == true && !next.busy) {
        final answer = next.messages.lastWhere((m) => m.role == Role.assistant,
            orElse: () => const ChatMessage(id: '', role: Role.assistant));
        if (next.pending == null && answer.text.isNotEmpty) {
          _say(answer.text, _generation);
        }
      }
    });
    WidgetsBinding.instance.addPostFrameCallback((_) => _listen());
  }

  Future<void> _listen() async {
    final turn = ++_generation;
    setState(() {
      _phase = LivePhase.listening;
      _error = null;
      _spoke = false;
      _lastVoice = null;
      _heard = '';
      _caption = '';
      _queuedChars = 0;
      _playbackError = null;
      _speechQueue = Future.value();
    });
    try {
      _native = !_useRecording &&
          await _recognizer.initialize(onError: (_) {
            if (mounted && _phase == LivePhase.listening) {
              _fail('Speech recognition paused. Tap resume or use recording.');
            }
          });
      if (!mounted || turn != _generation) return;
      if (_native) {
        await _recognizer.listen(
          listenOptions: SpeechListenOptions(
              localeId: speechLanguage(ref.read(languageProvider).code),
              listenFor: Duration(seconds: widget.maxSeconds),
              pauseFor: const Duration(milliseconds: 900),
              partialResults: true,
              cancelOnError: true,
              listenMode: ListenMode.dictation),
          onSoundLevelChange: (v) {
            if (mounted && turn == _generation) {
              setState(() => _level = ((v + 2) / 12).clamp(0, 1));
            }
          },
          onResult: (result) {
            if (!mounted || turn != _generation) return;
            setState(() => _heard = result.recognizedWords);
            if (result.finalResult && result.recognizedWords.trim().isNotEmpty) {
              _finishTurn(turn);
            }
          },
        );
        _limit = Timer(
            Duration(seconds: widget.maxSeconds), () => _finishTurn(turn));
        return;
      }
      await _speech.start();
    } catch (_) {
      return _fail('fos.assistant.mic_failed'.tr());
    }
    if (!mounted || turn != _generation) {
      await _speech.cancel();
      return;
    }
    _limit =
        Timer(Duration(seconds: widget.maxSeconds), () => _finishTurn(turn));
    _levels = _speech.levels().listen((level) {
      if (!mounted || turn != _generation) return;
      setState(() => _level = level);
      final now = DateTime.now();
      if (level > 0.35) {
        _spoke = true;
        _lastVoice = now;
      } else if (_spoke &&
          _lastVoice != null &&
          now.difference(_lastVoice!) > const Duration(milliseconds: 900)) {
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
    setState(() => _phase = LivePhase.understanding);
    await _stopListening();
    final String text;
    try {
      if (_native) {
        await _recognizer.stop();
        text = _heard.trim();
      } else {
        text = await _speech
            .stopAndTranscribe(speechLanguage(ref.read(languageProvider).code));
      }
      if (text.isEmpty) {
        if (mounted) _fail('No words heard yet. Tap resume to try again.');
        return;
      }
    } catch (e) {
      return _fail(e is ApiException
          ? e.message
          : 'Audio could not finish. Please try again.');
    }
    if (turn != _generation || !mounted) return;
    setState(() {
      _heard = text;
      _phase = LivePhase.working;
    });
    final assistant = ref.read(assistantProvider.notifier);
    await assistant.send(text, context: widget.runContext);
    if (turn != _generation || !mounted) return;
    await _speechQueue;
    if (turn != _generation || !mounted) return;
    final state = ref.read(assistantProvider);
    if (state.pending != null) {
      setState(() => _phase = LivePhase.review);
      final pending = state.pending!;
      final prompt =
          pending.question ?? pending.fields.map((f) => f.prompt).join('. ');
      if (prompt.isNotEmpty) {
        try {
          await _speech.speak(prompt,
              speechLanguageFor(prompt, ref.read(languageProvider).code),
              onCaption: (text) {
            if (mounted && turn == _generation) setState(() => _caption = text);
          });
        } catch (_) {}
      }
      return;
    }
    final answer = state.messages.lastWhere((m) => m.role == Role.assistant,
        orElse: () => const ChatMessage(id: '', role: Role.assistant));
    if (answer.error != null) return _fail(answer.error!);
    if (answer.text.isEmpty) return _listen();
    _queueAnswer(answer.text, turn, flush: true);
    await _speechQueue;
    if (!mounted || turn != _generation) return;
    if (_playbackError != null) return _fail(_playbackError!);
    await _listen();
  }

  void _queueAnswer(String text, int turn, {bool flush = false}) {
    if (text.length <= _queuedChars) return;
    final tail = text.substring(_queuedChars);
    final ends = RegExp(r'[.!?।](?:\s|$)').allMatches(tail).toList();
    final end = flush
        ? tail.length
        : ends.isEmpty
            ? 0
            : ends.last.end;
    if (end == 0) return;
    final chunk = speakableText(tail.substring(0, end));
    _queuedChars += end;
    if (chunk.isEmpty) return;
    _speechQueue = _speechQueue.then((_) async {
      if (!mounted || turn != _generation || _playbackError != null) return;
      setState(() => _phase = LivePhase.preparing);
      try {
        await _speech.speak(
            chunk, speechLanguageFor(chunk, ref.read(languageProvider).code),
            onCaption: (caption) {
          if (mounted && turn == _generation) {
            setState(() {
              _caption = caption;
              _phase = LivePhase.speaking;
            });
          }
        });
      } catch (e) {
        _playbackError = e is ApiException
            ? e.message
            : 'Audio playback paused. Please try again.';
      }
    });
  }

  Future<void> _say(String text, int turn) async {
    setState(() => _phase = LivePhase.preparing);
    try {
      final speakable = speakableText(text);
      final language =
          speechLanguageFor(speakable, ref.read(languageProvider).code);
      await _speech.speak(speakable, language, onCaption: (caption) {
        if (mounted && turn == _generation) {
          setState(() {
            _phase = LivePhase.speaking;
            _caption = caption;
          });
        }
      });
    } catch (e) {
      return _fail(e is ApiException
          ? e.message
          : 'Audio could not finish. Please try again.');
    }
    if (mounted && turn == _generation && _phase == LivePhase.speaking) {
      await _listen();
    }
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
    await _recognizer.cancel();
    await _speech.cancel();
    await _speech.stopSpeaking();
    _assistant.stop();
  }

  Future<void> _end() async {
    await _interrupt();
    if (mounted) Navigator.pop(context);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive) {
      _interrupt();
      if (mounted) setState(() => _phase = LivePhase.muted);
    }
  }

  @override
  void dispose() {
    _generation++;
    WidgetsBinding.instance.removeObserver(this);
    _clock?.cancel();
    _assistantListener?.close();
    _recognizer.cancel();
    _limit?.cancel();
    _levels?.cancel();
    _speech.cancel();
    _speech.stopSpeaking();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(assistantProvider);
    final seconds = DateTime.now().difference(_started).inSeconds;
    final timer =
        '${(seconds ~/ 60).toString().padLeft(2, '0')}:${(seconds % 60).toString().padLeft(2, '0')}';
    final busy = {LivePhase.working, LivePhase.speaking, LivePhase.preparing}
        .contains(_phase);
    final status = _phase == LivePhase.error
        ? _error!
        : _phase == LivePhase.working && state.status.isNotEmpty
            ? state.status
            : livePhaseLabel(_phase);
    return PopScope(
      onPopInvokedWithResult: (didPop, _) {
        if (didPop) _interrupt();
      },
      child: Scaffold(
        body: FarmBackground(
            child: SafeArea(
                child: Column(children: [
          Padding(
              padding: const EdgeInsets.fromLTRB(24, 16, 16, 0),
              child: Row(children: [
                const Icon(Icons.circle, size: 8, color: AppColors.primary),
                const SizedBox(width: 8),
                Text('MITRA VOICE',
                    style: TextStyle(
                        letterSpacing: 2,
                        fontSize: 11,
                        color: mutedColor(context))),
                const Spacer(),
                IconButton(
                    tooltip: 'End call',
                    onPressed: _end,
                    icon: const Icon(Icons.close_rounded)),
              ])),
          Expanded(
              child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 24),
                  child: Column(children: [
                    const SizedBox(height: 24),
                    Text('A little company.\nA lot of farm wisdom.',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            fontSize: 26,
                            height: 1.25,
                            fontWeight: FontWeight.w600,
                            color: inkColor(context))),
                    const SizedBox(height: 20),
                    MitraOrb(
                        size: 230,
                        active: _phase != LivePhase.muted,
                        speaking: _phase == LivePhase.speaking,
                        level: _level),
                    const SizedBox(height: 12),
                    Text(timer,
                        style: const TextStyle(
                            fontSize: 18, fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    Semantics(
                        liveRegion: true,
                        child: Text(status,
                            textAlign: TextAlign.center,
                            style: TextStyle(color: mutedColor(context)))),
                    const SizedBox(height: 24),
                    AnimatedSwitcher(
                        duration: const Duration(milliseconds: 280),
                        child: Text(
                          _caption.isNotEmpty
                              ? _caption
                              : _heard.isNotEmpty
                                  ? '“$_heard”'
                                  : 'Tell me what is on your mind.',
                          key:
                              ValueKey(_caption.isNotEmpty ? _caption : _heard),
                          textAlign: TextAlign.center,
                          style: TextStyle(
                              fontSize: 19,
                              height: 1.55,
                              color: inkColor(context)),
                        )),
                    if (state.pending != null &&
                        !state.busy &&
                        _phase == LivePhase.review) ...[
                      const SizedBox(height: 20),
                      PendingCard(pending: state.pending!),
                    ],
                    const SizedBox(height: 20),
                  ]))),
          if (_phase == LivePhase.error)
            TextButton(
                onPressed: () {
                  _useRecording = true;
                  _listen();
                },
                child: const Text('Use recording instead')),
          if (_phase == LivePhase.error || _phase == LivePhase.muted)
            TextButton.icon(
                onPressed: _listen,
                icon: const Icon(Icons.refresh),
                label: const Text('Resume conversation')),
          Padding(
              padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
              child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                  children: [
                    IconButton.filledTonal(
                        tooltip: 'Mute microphone',
                        onPressed: () async {
                          HapticFeedback.selectionClick();
                          await _interrupt();
                          if (mounted) setState(() => _phase = LivePhase.muted);
                        },
                        icon: Icon(_phase == LivePhase.muted
                            ? Icons.mic_off_rounded
                            : Icons.mic_rounded),
                        style: IconButton.styleFrom(
                            minimumSize: const Size(56, 56))),
                    IconButton.filled(
                        tooltip: 'End call',
                        onPressed: () {
                          HapticFeedback.mediumImpact();
                          _end();
                        },
                        style: IconButton.styleFrom(
                            backgroundColor: const Color(0xFFB7604E),
                            minimumSize: const Size(70, 60)),
                        icon: const Icon(Icons.call_end_rounded)),
                    IconButton.filledTonal(
                        tooltip: busy ? 'Interrupt Mitra' : 'Done speaking',
                        onPressed: busy
                            ? () async {
                                await _interrupt();
                                if (mounted) await _listen();
                              }
                            : _phase == LivePhase.listening
                                ? () => _finishTurn(_generation)
                                : null,
                        style: IconButton.styleFrom(
                            minimumSize: const Size(56, 56)),
                        icon: Icon(busy
                            ? Icons.pan_tool_alt_outlined
                            : Icons.check_rounded)),
                  ])),
          Padding(
              padding: const EdgeInsets.only(bottom: 16),
              child: Text('Stay in the conversation. Review every change.',
                  style: TextStyle(fontSize: 11, color: mutedColor(context)))),
        ]))),
      ),
    );
  }
}
