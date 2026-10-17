import 'dart:async';
import 'dart:math' as math;
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/session.dart';
import 'tour_steps.dart';

class TourStop {
  const TourStop(this.anchor, this.title, this.body);
  final String anchor, title, body;
}

/// Only non-sensitive tour position is stored. No farm data or permissions change.
class TourProgress {
  TourProgress(this.prefs, this.owner);
  final SharedPreferences prefs;
  final String owner;
  String key(String scope) => 'mitra_tour_v1:$owner:$scope';
  int read(String scope) => prefs.getInt(key(scope)) ?? 0;
  Future<void> write(String scope, int step) async {
    await prefs.setInt(key(scope), step);
  }
}

class AppTour extends ConsumerWidget {
  const AppTour({super.key, required this.scope, required this.child});
  final String scope;
  final Widget child;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(authProvider.select((a) => a.session?.id));
    String? uid;
    try {
      uid = FirebaseAuth.instance.currentUser?.uid;
    } catch (_) {/* Local/test mode. */}
    return TourHost(
        owner: uid ?? session,
        scope: scope,
        steps: tourSteps(scope),
        child: child);
  }
}

class _TourScope extends InheritedWidget {
  const _TourScope({required this.state, required super.child});
  final TourHostState state;
  static TourHostState? of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<_TourScope>()?.state;
  @override
  bool updateShouldNotify(_TourScope oldWidget) => state != oldWidget.state;
}

/// Wrap the exact control, not a guessed screen coordinate or translated label.
class TourAnchor extends StatefulWidget {
  const TourAnchor({super.key, required this.id, required this.child});
  final String id;
  final Widget child;
  @override
  State<TourAnchor> createState() => _TourAnchorState();
}

class _TourAnchorState extends State<TourAnchor> {
  TourHostState? host;
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    host?.unregister(widget.id, context);
    host = _TourScope.of(context);
    host?.register(widget.id, context);
  }

  @override
  void didUpdateWidget(TourAnchor oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.id != widget.id) {
      host?.unregister(oldWidget.id, context);
      host?.register(widget.id, context);
    }
  }

  @override
  void dispose() {
    host?.unregister(widget.id, context);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}

class TourReplayButton extends StatelessWidget {
  const TourReplayButton({super.key});
  @override
  Widget build(BuildContext context) => TourAnchor(
      id: 'replay',
      child: IconButton(
        tooltip: 'Take a tour',
        icon: const Icon(Icons.explore_outlined),
        onPressed: _TourScope.of(context)?.start,
      ));
}

/// Select a contextual guide without rebuilding the screen or discarding its forms.
class TourSection extends StatefulWidget {
  const TourSection({super.key, required this.scope, required this.child});
  final String scope;
  final Widget child;
  @override
  State<TourSection> createState() => _TourSectionState();
}

class _TourSectionState extends State<TourSection> {
  void sync() {
    final host = _TourScope.of(context);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && host != null && host.mounted) host.section(widget.scope);
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    sync();
  }

  @override
  void didUpdateWidget(TourSection oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.scope != widget.scope) sync();
  }

  @override
  Widget build(BuildContext context) => widget.child;
}

Rect tourCardRect(Rect target, Size card, Size viewport, EdgeInsets safe) {
  final left = (target.center.dx - card.width / 2)
      .clamp(12.0, math.max(12.0, viewport.width - card.width - 12));
  final bottom = viewport.height - safe.bottom - 12;
  final top = target.bottom + 16 + card.height <= bottom
      ? target.bottom + 16
      : target.top - card.height - 16 >= safe.top + 12
          ? target.top - card.height - 16
          : math.max(safe.top + 12, bottom - card.height);
  return Rect.fromLTWH(left.toDouble(), top, card.width, card.height);
}

class TourHost extends StatefulWidget {
  const TourHost(
      {super.key,
      required this.owner,
      required this.scope,
      required this.steps,
      required this.child,
      this.autoStart = true});
  final String? owner;
  final String scope;
  final List<TourStop> steps;
  final Widget child;
  final bool autoStart;
  @override
  State<TourHost> createState() => TourHostState();
}

class TourHostState extends State<TourHost>
    with SingleTickerProviderStateMixin, WidgetsBindingObserver {
  static TourHostState? _active;
  String? _section;
  String get _scope => _section ?? widget.scope;
  List<TourStop> get _steps =>
      _section == null ? widget.steps : tourSteps(_scope);
  void section(String value) {
    if (_section == value) return;
    _stop();
    setState(() => _section = value);
    _restore();
  }

  final anchors = <String, BuildContext>{};
  final _surface = GlobalKey(), _card = GlobalKey();
  final _focus = FocusScopeNode(debugLabel: 'Mitra guide');
  final _nextFocus = FocusNode(debugLabel: 'Next tour stop');
  FocusNode? _previousFocus;
  Timer? _autoTimer;
  late final Ticker _ticker;
  TourProgress? _progress;
  int? _index;
  Rect? _rect;
  Size _cardSize = const Size(330, 280);
  Duration _lastTick = Duration.zero, _missingSince = Duration.zero;
  BuildContext? _lastTarget;
  bool _scrollPending = false;
  int _generation = 0;
  Future<void> _writes = Future.value();
  void register(String id, BuildContext context) => anchors[id] = context;
  void unregister(String id, BuildContext context) {
    if (anchors[id] == context) anchors.remove(id);
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _ticker = createTicker(_track);
    _restore();
  }

  @override
  void didUpdateWidget(TourHost oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.owner != widget.owner || oldWidget.scope != widget.scope) {
      _stop();
      _progress = null;
      _restore();
    }
  }

  Future<void> _restore() async {
    final generation = ++_generation;
    _autoTimer?.cancel();
    if (widget.owner == null) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      if (!mounted || generation != _generation) return;
      _progress = TourProgress(prefs, widget.owner!);
      final saved = _progress!.read(_scope);
      if (!widget.autoStart ||
          _scope == 'onboarding' ||
          saved < 0 ||
          _steps.isEmpty) {
        return;
      }
      _autoTimer = Timer(const Duration(milliseconds: 800), () {
        if (!mounted ||
            generation != _generation ||
            !(ModalRoute.of(context)?.isCurrent ?? true) ||
            MediaQuery.viewInsetsOf(context).bottom > 0 ||
            _active != null) {
          return;
        }
        _begin(saved.clamp(0, _steps.length - 1));
      });
    } catch (_) {/* Replay remains available when storage cannot be read. */}
  }

  void _remember(int value) {
    final progress = _progress, scope = _scope;
    if (progress != null) {
      _writes = _writes
          .then((_) => progress.write(scope, value))
          .catchError((Object _) {});
    }
  }

  void start() {
    if (_steps.isEmpty || (_active != null && _active != this)) return;
    FocusManager.instance.primaryFocus?.unfocus();
    _begin(0);
  }

  void _begin(int step) {
    if (!mounted) return;
    _active = this;
    _lastTick = Duration.zero;
    _previousFocus = FocusManager.instance.primaryFocus;
    _move(step);
    if (!_ticker.isActive) _ticker.start();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && _index != null) _nextFocus.requestFocus();
    });
  }

  void _move(int step) {
    HapticFeedback.selectionClick();
    _lastTarget = null;
    _missingSince = _lastTick;
    setState(() {
      _index = step;
      _rect = null;
    });
    _remember(step);
  }

  void close() {
    _remember(-1);
    _stop();
    if (mounted) setState(() {});
    if (_previousFocus?.context != null) _previousFocus?.requestFocus();
  }

  void _stop() {
    _autoTimer?.cancel();
    if (_ticker.isActive) _ticker.stop();
    if (_active == this) _active = null;
    _index = null;
    _rect = null;
    _lastTarget = null;
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed) _autoTimer?.cancel();
    if (state != AppLifecycleState.resumed && _index != null) {
      _stop();
      if (mounted) setState(() {});
    }
  }

  void _track(Duration elapsed) {
    _lastTick = elapsed;
    if (!mounted || _index == null) return;
    if (!(ModalRoute.of(context)?.isCurrent ?? true)) {
      _stop();
      setState(() {});
      return;
    }
    final target = anchors[_steps[_index!].anchor];
    final render = target?.findRenderObject();
    final surface = _surface.currentContext?.findRenderObject();
    if (render is! RenderBox ||
        !render.attached ||
        !render.hasSize ||
        render.size.isEmpty ||
        surface is! RenderBox ||
        !surface.hasSize) {
      if (_rect != null) setState(() => _rect = null);
      if (elapsed - _missingSince > const Duration(seconds: 4)) {
        if (_index! + 1 < _steps.length) {
          _move(_index! + 1);
        } else {
          close();
        }
      }
      return;
    }
    if (_lastTarget != target && !_scrollPending) {
      _lastTarget = target;
      _scrollPending = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _scrollPending = false;
        if (mounted && target!.mounted && _index != null) {
          Scrollable.ensureVisible(target,
              alignment: .35, duration: Duration.zero);
        }
      });
    }
    final offset = surface.globalToLocal(render.localToGlobal(Offset.zero));
    final rect =
        (offset & render.size).inflate(5).intersect(Offset.zero & surface.size);
    if (rect.isEmpty) {
      if (_rect != null) setState(() => _rect = null);
      if (elapsed - _missingSince > const Duration(seconds: 4)) {
        if (_index! + 1 < _steps.length) {
          _move(_index! + 1);
        } else {
          close();
        }
      }
      return;
    }
    final card = _card.currentContext?.findRenderObject();
    final size = card is RenderBox && card.hasSize ? card.size : _cardSize;
    if (rect != _rect || size != _cardSize) {
      setState(() {
        _rect = rect;
        _cardSize = size;
      });
    }
  }

  @override
  void dispose() {
    ++_generation;
    _stop();
    _ticker.dispose();
    WidgetsBinding.instance.removeObserver(this);
    _focus.dispose();
    _nextFocus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final step = _index == null ? null : _steps[_index!];
    return _TourScope(
        state: this,
        child: PopScope(
          canPop: step == null,
          onPopInvokedWithResult: (didPop, _) {
            if (!didPop && step != null) close();
          },
          child: Stack(key: _surface, fit: StackFit.expand, children: [
            ExcludeFocus(
                excluding: step != null,
                child: ExcludeSemantics(
                    excluding: step != null, child: widget.child)),
            if (step != null)
              LayoutBuilder(builder: (context, bounds) {
                final safe = MediaQuery.paddingOf(context);
                final maxWidth = math.min(350.0, bounds.maxWidth - 24);
                final cardRect = tourCardRect(
                    _rect ?? Rect.fromLTWH(12, safe.top, 1, 1),
                    Size(maxWidth, _cardSize.height),
                    bounds.biggest,
                    safe);
                return Stack(children: [
                  const Positioned.fill(
                      child: ModalBarrier(
                          dismissible: false, color: Colors.transparent)),
                  Positioned.fill(
                      child: IgnorePointer(
                          child: CustomPaint(
                              painter: _TourPaint(_rect, cardRect)))),
                  Positioned(
                    left: cardRect.left,
                    top: cardRect.top,
                    width: maxWidth,
                    child: Semantics(
                      scopesRoute: true,
                      namesRoute: true,
                      label: 'Mitra guide',
                      explicitChildNodes: true,
                      child: FocusScope(
                        node: _focus,
                        autofocus: true,
                        child: Shortcuts(
                            shortcuts: {
                              const SingleActivator(LogicalKeyboardKey.escape):
                                  const DismissIntent()
                            },
                            child: Actions(
                              actions: {
                                DismissIntent: CallbackAction<DismissIntent>(
                                    onInvoke: (_) {
                                  close();
                                  return null;
                                })
                              },
                              child: Material(
                                key: _card,
                                elevation: 0,
                                color: Theme.of(context).brightness ==
                                        Brightness.dark
                                    ? const Color(0xff243229)
                                    : const Color(0xfffaf9f3),
                                borderRadius: BorderRadius.circular(24),
                                clipBehavior: Clip.antiAlias,
                                child: ConstrainedBox(
                                  constraints: BoxConstraints(
                                      maxHeight: math.max(
                                          100,
                                          bounds.maxHeight -
                                              safe.vertical -
                                              24)),
                                  child: SingleChildScrollView(
                                      padding: const EdgeInsets.all(20),
                                      child: Column(
                                          crossAxisAlignment:
                                              CrossAxisAlignment.start,
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            Row(children: [
                                              const Icon(Icons.spa_outlined,
                                                  size: 17),
                                              const SizedBox(width: 8),
                                              Expanded(
                                                  child: Text(
                                                      'MITRA’S LITTLE GUIDE · ${_index! + 1}/${_steps.length}',
                                                      style: const TextStyle(
                                                          fontSize: 10,
                                                          letterSpacing: .8))),
                                              IconButton(
                                                  tooltip: 'Close tour',
                                                  onPressed: close,
                                                  icon: const Icon(Icons.close,
                                                      size: 18))
                                            ]),
                                            const SizedBox(height: 6),
                                            Semantics(
                                                header: true,
                                                liveRegion: true,
                                                child: Text(
                                                    _rect == null
                                                        ? 'Finding your next stop…'
                                                        : step.title,
                                                    style: const TextStyle(
                                                        fontSize: 22,
                                                        fontWeight:
                                                            FontWeight.w600,
                                                        height: 1.2))),
                                            const SizedBox(height: 12),
                                            Text(
                                                _rect == null
                                                    ? 'Waiting for this control to be ready. You can skip at any time.'
                                                    : step.body,
                                                style: const TextStyle(
                                                    fontSize: 14, height: 1.6)),
                                            const SizedBox(height: 18),
                                            Wrap(
                                                alignment:
                                                    WrapAlignment.spaceBetween,
                                                spacing: 8,
                                                runSpacing: 4,
                                                children: [
                                                  TextButton(
                                                      onPressed: close,
                                                      child: const Text(
                                                          'Skip tour')),
                                                  TextButton(
                                                      onPressed: _index == 0
                                                          ? null
                                                          : () => _move(
                                                              _index! - 1),
                                                      child:
                                                          const Text('Back')),
                                                  FilledButton(
                                                      focusNode: _nextFocus,
                                                      onPressed: _rect == null
                                                          ? null
                                                          : () => _index! + 1 <
                                                                  _steps.length
                                                              ? _move(
                                                                  _index! + 1)
                                                              : close(),
                                                      child: Text(_index! + 1 ==
                                                              _steps.length
                                                          ? 'Done'
                                                          : 'Next'))
                                                ]),
                                          ])),
                                ),
                              ),
                            )),
                      ),
                    ),
                  ),
                ]);
              }),
          ]),
        ));
  }
}

class _TourPaint extends CustomPainter {
  _TourPaint(this.target, this.card);
  final Rect? target;
  final Rect card;
  @override
  void paint(Canvas canvas, Size size) {
    final shade = Path()
      ..fillType = PathFillType.evenOdd
      ..addRect(Offset.zero & size);
    if (target != null && !target!.isEmpty) {
      shade.addRRect(
          RRect.fromRectAndRadius(target!, const Radius.circular(14)));
    }
    canvas.drawPath(shade, Paint()..color = const Color(0x881b261a));
    if (target != null && !target!.isEmpty) {
      final p = Paint()
        ..color = const Color(0xffdcebb1)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5;
      canvas.drawRRect(
          RRect.fromRectAndRadius(target!, const Radius.circular(14)), p);
      final below = card.top >= target!.bottom;
      canvas.drawLine(
          Offset(target!.center.dx, below ? target!.bottom : target!.top),
          Offset(card.center.dx, below ? card.top : card.bottom),
          p);
    }
  }

  @override
  bool shouldRepaint(_TourPaint oldDelegate) =>
      target != oldDelegate.target || card != oldDelegate.card;
}
