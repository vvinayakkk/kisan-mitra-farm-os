// Run from mobile: flutter test tool/generate_launcher_icons.dart
// Exports the actual in-app companion, keeping launcher art consistent.
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skyview_app/ui/mitra_orb.dart';

void main() {
  testWidgets('export Saathi launcher resources', (tester) async {
    tester.view.physicalSize = const Size(108, 108);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final boundary = GlobalKey();
    Future<void> render(bool foreground) async {
      await tester.pumpWidget(MediaQuery(
        data: const MediaQueryData(disableAnimations: true),
        child: Directionality(textDirection: TextDirection.ltr,
          child: RepaintBoundary(key: boundary,
            child: ColoredBox(color: foreground ? Colors.transparent : const Color(0xFFF7F6F2),
              child: Center(child: MitraOrb(size: foreground ? 70 : 94, active: false)))))));
      await tester.pump();
    }
    Future<void> export(String path, int size) async {
      await tester.runAsync(() async {
        final image = await (boundary.currentContext!.findRenderObject() as RenderRepaintBoundary).toImage(pixelRatio: size / 108);
        final data = await image.toByteData(format: ui.ImageByteFormat.png);
        final file = File(path);
        await file.parent.create(recursive: true);
        await file.writeAsBytes(data!.buffer.asUint8List());
        image.dispose();
      });
    }
    const densities = {'mdpi': 1.0, 'hdpi': 1.5, 'xhdpi': 2.0, 'xxhdpi': 3.0, 'xxxhdpi': 4.0};
    await render(true);
    for (final density in densities.entries) {
      await export('android/app/src/main/res/drawable-${density.key}/ic_launcher_foreground.png', (108 * density.value).round());
    }
    await render(false);
    for (final density in densities.entries) {
      await export('android/app/src/main/res/mipmap-${density.key}/ic_launcher.png', (48 * density.value).round());
    }
    await export('assets/branding/saathi-launcher.png', 1024);
  });
}
