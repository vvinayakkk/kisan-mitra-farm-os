import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../ui/mitra_orb.dart';

/// A launch transition, not a welcome page. Routing restores the saved session.
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});
  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final _arrival = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 1100))
    ..forward();
  @override
  void dispose() {
    _arrival.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final dark = Theme.of(context).brightness == Brightness.dark;
    final reduced = MediaQuery.disableAnimationsOf(context);
    final ink = dark ? const Color(0xFFF4F3EC) : const Color(0xFF29372B);
    return Scaffold(
        backgroundColor:
            dark ? const Color(0xFF19221C) : const Color(0xFFF7F6F2),
        body: SafeArea(child: LayoutBuilder(builder: (context, box) {
          final size = math.min(box.maxWidth * .62, 260.0);
          return AnimatedBuilder(
              animation: _arrival,
              builder: (context, _) {
                final t = reduced ? 1.0 : _arrival.value;
                final rise = Curves.easeOutBack.transform(t);
                return Stack(children: [
                  Positioned.fill(
                      child: CustomPaint(painter: _FieldLines(dark))),
                  Center(
                      child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Transform.translate(
                        offset: Offset(0, (1 - rise) * 28),
                        child: Transform.scale(
                            scale: .8 + .2 * rise,
                            child: Opacity(
                                opacity: (t * 3).clamp(0, 1),
                                child: MitraOrb(size: size)))),
                    const SizedBox(height: 24),
                    Opacity(
                        opacity: (t * 2).clamp(0, 1),
                        child: Text('kisan mitra',
                            style: TextStyle(
                                color: ink,
                                fontSize: 36,
                                fontWeight: FontWeight.w600,
                                letterSpacing: -1.4))),
                    const SizedBox(height: 10),
                    Text('A little company. A better farm day.',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                            color: ink.withValues(alpha: .78), fontSize: 13)),
                  ])),
                  Positioned(
                      bottom: 40,
                      left: 24,
                      right: 24,
                      child: Column(children: [
                        SizedBox(
                            width: 22,
                            height: 3,
                            child: LinearProgressIndicator(
                                value: reduced ? 1 : null,
                                borderRadius: BorderRadius.circular(3),
                                backgroundColor: ink.withValues(alpha: .08),
                                color: ink.withValues(alpha: .35))),
                        const SizedBox(height: 14),
                        Text('Making room for your day…',
                            style: TextStyle(
                                color: ink.withValues(alpha: .72),
                                fontSize: 11)),
                      ])),
                ]);
              });
        })));
  }
}

class _FieldLines extends CustomPainter {
  _FieldLines(this.dark);
  final bool dark;
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color =
          (dark ? Colors.white : const Color(0xFF718362)).withValues(alpha: .08)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    for (var i = 0; i < 5; i++) {
      final y = size.height * .82 + i * 26;
      canvas.drawPath(
          Path()
            ..moveTo(-40, y)
            ..cubicTo(size.width * .32, y - 100, size.width * .64, y + 80,
                size.width + 40, y - 32),
          paint);
    }
  }

  @override
  bool shouldRepaint(_FieldLines old) => old.dark != dark;
}
