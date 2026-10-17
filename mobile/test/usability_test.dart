import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:skyview_app/ui/form_sheet.dart';
import 'package:skyview_app/ui/loader.dart';
import 'package:skyview_app/ui/mitra_orb.dart';
import 'package:skyview_app/utils/constants.dart';
import 'l10n.dart';

Future<void> capture(GlobalKey key, String name, WidgetTester tester) async {
  if (!const bool.fromEnvironment('CAPTURE_REVIEW')) return;
  await tester.runAsync(() async {
    final image =
        await (key.currentContext!.findRenderObject() as RenderRepaintBoundary)
            .toImage(pixelRatio: 2);
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    final dir = Directory(const String.fromEnvironment('REVIEW_OUTPUT',
        defaultValue: 'work/usability'));
    await dir.create(recursive: true);
    await File('${dir.path}/$name.png')
        .writeAsBytes(bytes!.buffer.asUint8List());
  });
}

void main() {
  setUpAll(() async {
    loadEnglish();
    final font = FontLoader('Poppins');
    for (final weight in ['Regular', 'Medium', 'SemiBold', 'Bold']) {
      font.addFont(Future.value(ByteData.sublistView(
          File('assets/fonts/Poppins-$weight.ttf').readAsBytesSync())));
    }
    await font.load();
    var root = Platform.environment['FLUTTER_ROOT'];
    var dir = File(Platform.resolvedExecutable).parent;
    while (root == null && dir.parent.path != dir.path) {
      if (File(
              '${dir.path}/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf')
          .existsSync()) { root = dir.path; }
      dir = dir.parent;
    }
    if (root == null) throw StateError('Flutter font directory not found');
    await (FontLoader('MaterialIcons')
          ..addFont(Future.value(ByteData.sublistView(File(
                  '$root/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf')
              .readAsBytesSync()))))
        .load();
  });
  setUp(() => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
      .setMockMethodCallHandler(
          const MethodChannel('plugin.csdcorp.com/speech_to_text'),
          (_) async => false));
  testWidgets('dirty form survives cancel/back and focuses inline validation',
      (tester) async {
    tester.view.physicalSize = const Size(430, 932);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final boundary = GlobalKey();
    Map<String, Object?>? saved;
    await tester.pumpWidget(ProviderScope(
        child: RepaintBoundary(
            key: boundary,
            child: MaterialApp(debugShowCheckedModeBanner: false,
                theme: buildAppTheme(dark: false),
                home: Builder(
                    builder: (context) => Scaffold(
                        appBar: AppBar(title: const Text('My notebook')),
                        body: Center(
                            child: FilledButton(
                                onPressed: () async {
                                  saved = await showFormSheet(context,
                                      title: 'Add a field',
                                      fields: const [
                                        FieldSpec('name', 'Field name',
                                            required: true),
                                        FieldSpec('area', 'Area in hectares',
                                            kind: FieldKind.number,
                                            required: true)
                                      ]);
                                },
                                child: const Text('Add field')))))))));
    await tester.tap(find.text('Add field'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextField).first, 'Riverside');
    await tester.binding.handlePopRoute();
    await tester.pumpAndSettle();
    expect(find.text('Discard these changes?'), findsOneWidget);
    await capture(boundary, '18-protected-edit', tester);
    await tester.tap(find.text('Keep editing'));
    await tester.pumpAndSettle();
    expect(find.text('Riverside'), findsOneWidget);
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(
        tester
            .widget<TextField>(find.byType(TextField).last)
            .focusNode!
            .hasFocus,
        isTrue);
    expect(find.textContaining('Area in hectares').evaluate().length,
        greaterThan(1));
    await capture(boundary, '19-inline-validation', tester);
    await tester.enterText(find.byType(TextField).last, 'NaN');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(saved, isNull);
    await tester.enterText(find.byType(TextField).last, '2.5');
    await tester.tap(find.text('Save'));
    await tester.pumpAndSettle();
    expect(saved, {'name': 'Riverside', 'area': 2.5});
  });
  testWidgets('failed refresh retains useful content with a recoverable error',
      (tester) async {
    tester.view.physicalSize = const Size(430, 932);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final key = GlobalKey<LoaderState<int>>();
    final boundary = GlobalKey();
    var fail = false;
    await tester.pumpWidget(ProviderScope(
        child: RepaintBoundary(
            key: boundary,
            child: MaterialApp(debugShowCheckedModeBanner: false,
                theme: buildAppTheme(dark: false),
                home: Scaffold(
                    appBar: AppBar(title: const Text('Your farm')),
                    body: Loader<int>(
                        key: key,
                        load: () async {
                          if (fail) throw StateError('network');
                          return 6;
                        },
                        builder: (_, v) => Center(
                            child: Text('$v saved tasks',
                                style: const TextStyle(fontSize: 28)))))))));
    await tester.pumpAndSettle();
    expect(find.text('6 saved tasks'), findsOneWidget);
    fail = true;
    await key.currentState!.reload();
    await tester.pumpAndSettle();
    expect(find.text('6 saved tasks'), findsOneWidget);
    expect(find.textContaining('Keeping your previous view'), findsOneWidget);
    await capture(boundary, '20-refresh-recovery', tester);
    fail = false;
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Keeping your previous view'), findsNothing);
  });
  testWidgets(
      'reduced motion and inactive companion do not keep scheduling animation frames',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(debugShowCheckedModeBanner: false,
        home: MediaQuery(
            data: MediaQueryData(disableAnimations: true), child: MitraOrb())));
    await tester.pumpAndSettle();
    expect(tester.binding.transientCallbackCount, 0);
    await tester.pumpWidget(const MaterialApp(debugShowCheckedModeBanner: false, home: MitraOrb(active: false)));
    await tester.pumpAndSettle();
    expect(tester.binding.transientCallbackCount, 0);
  });
  testWidgets('late stale reload cannot overwrite a newer response',
      (tester) async {
    final requests = <Completer<int>>[];
    final key = GlobalKey<LoaderState<int>>();
    await tester.pumpWidget(ProviderScope(
        child: MaterialApp(debugShowCheckedModeBanner: false,
            home: Scaffold(
                body: Loader<int>(
                    key: key,
                    load: () {
                      final c = Completer<int>();
                      requests.add(c);
                      return c.future;
                    },
                    builder: (_, v) => Text('Version $v'))))));
    final newest = key.currentState!.reload();
    requests[1].complete(2);
    await newest;
    await tester.pump();
    requests[0].complete(1);
    await tester.pump();
    expect(find.text('Version 2'), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
  });
  testWidgets(
      'uncached loading has labelled placeholders and resolves without invented values',
      (tester) async {
    tester.view.physicalSize = const Size(430, 932);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final waiting = Completer<int>();
    final boundary = GlobalKey();
    await tester.pumpWidget(ProviderScope(
        child: RepaintBoundary(
            key: boundary,
            child: MaterialApp(debugShowCheckedModeBanner: false,
                theme: buildAppTheme(dark: false),
                home: Scaffold(
                    appBar: AppBar(title: const Text('My notebook')),
                    body: Loader<int>(
                        loading: 'Opening your saved records…',
                        load: () => waiting.future,
                        builder: (_, v) => Text('$v records')))))));
    expect(find.byType(ContentSkeleton), findsOneWidget);
    expect(find.text('0 records'), findsNothing);
    await capture(boundary, '22-loading-placeholder', tester);
    waiting.complete(6);
    await tester.pumpAndSettle();
    expect(find.byType(ContentSkeleton), findsNothing);
    expect(find.text('6 records'), findsOneWidget);
  });
}
