import 'dart:math' as math;
import 'package:flutter/material.dart';

/// A quiet, expressive companion drawn at device resolution.
class MitraOrb extends StatefulWidget {
  const MitraOrb(
      {super.key,
      this.size = 220,
      this.active = true,
      this.speaking = false,
      this.level = 0});
  final double size, level;
  final bool active, speaking;
  @override
  State<MitraOrb> createState() => _MitraOrbState();
}

class _MitraOrbState extends State<MitraOrb>
    with SingleTickerProviderStateMixin {
  late final _motion =
      AnimationController(vsync: this, duration: const Duration(seconds: 4));
  void _updateMotion() {
    if (!MediaQuery.disableAnimationsOf(context) &&
        TickerMode.valuesOf(context).enabled &&
        widget.active) {
      if (!_motion.isAnimating) _motion.repeat();
    } else {
      _motion.stop();
    }
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _updateMotion();
  }

  @override
  void didUpdateWidget(MitraOrb old) {
    super.didUpdateWidget(old);
    _updateMotion();
  }

  @override
  void dispose() {
    _motion.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Semantics(
      label: 'Mitra, your farm companion',
      image: true,
      child: AnimatedBuilder(
          animation: _motion,
          builder: (_, __) {
            final t =
                MediaQuery.disableAnimationsOf(context) ? 0.0 : _motion.value;
            return Transform.translate(
                offset: Offset(
                    0, widget.active ? math.sin(t * math.pi * 2) * 5 : 0),
                child: RepaintBoundary(
                    child: CustomPaint(
                        size: Size.square(widget.size),
                        painter:
                            _OrbPainter(t, widget.speaking, widget.level))));
          }));
}

class _OrbPainter extends CustomPainter {
  _OrbPainter(this.t, this.speaking, this.level);
  final double t, level;
  final bool speaking;
  @override
  void paint(Canvas c, Size s) {
    final center = Offset(s.width / 2, s.height / 2), r = s.width * .43;
    c.drawOval(
        Rect.fromCenter(
            center: Offset(center.dx, s.height * .94),
            width: r * 1.4,
            height: r * .13),
        Paint()
          ..color = const Color(0x1852734D)
          ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 9));
    c.drawCircle(
        center, r + 9 + level * 8, Paint()..color = const Color(0x1052734D));
    c.drawCircle(
        center,
        r,
        Paint()
          ..shader = const RadialGradient(
              center: Alignment(-.55, -.65),
              radius: 1.15,
              colors: [
                Color(0xFFF5FFE9),
                Color(0xFFCBDDB6),
                Color(0xFF8CA882)
              ]).createShader(Rect.fromCircle(center: center, radius: r)));
    final blink = t > .92 && t < .96;
    for (final x in [-.24, .24]) {
      final eye = center + Offset(r * x, -r * .03);
      c.drawOval(
          Rect.fromCenter(
              center: eye, width: r * .085, height: blink ? r * .025 : r * .13),
          Paint()..color = const Color(0xFF354536));
      if (!blink) {
        c.drawCircle(eye + Offset(-r * .015, -r * .025), r * .017,
            Paint()..color = Colors.white);
      }
    }
    final mouth = Rect.fromCenter(
        center: center + Offset(0, r * .09),
        width: r * .12,
        height: r * (speaking ? .09 + .05 * math.sin(t * 40).abs() : .07));
    c.drawArc(
        mouth,
        0,
        math.pi,
        false,
        Paint()
          ..color = const Color(0xFF354536)
          ..style = PaintingStyle.stroke
          ..strokeWidth = r * .025
          ..strokeCap = StrokeCap.round);
    for (final x in [-.37, .37]) {
      c.drawOval(
          Rect.fromCenter(
              center: center + Offset(r * x, r * .1),
              width: r * .13,
              height: r * .055),
          Paint()..color = const Color(0x339B8068));
    }
  }

  @override
  bool shouldRepaint(_OrbPainter old) =>
      t != old.t || speaking != old.speaking || level != old.level;
}
