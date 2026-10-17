import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:skyview_app/tour/app_tour.dart';

const stops = [
  TourStop('first', 'Meet your farm', 'This is your first control.'),
  TourStop('second', 'Your next step', 'Use this second control.')
];
Widget app(
        {String owner = 'one',
        bool missing = false,
        VoidCallback? action,
        double scale = 1}) =>
    MaterialApp(
      home: MediaQuery(
          data: MediaQueryData(
              size: const Size(390, 844), textScaler: TextScaler.linear(scale)),
          child: TourHost(
            owner: owner,
            scope: 'test',
            steps: stops,
            child: Scaffold(
                appBar: AppBar(actions: const [TourReplayButton()]),
                body: Column(children: [
                  if (!missing)
                    TourAnchor(
                        id: 'first',
                        child: FilledButton(
                            onPressed: action ?? () {},
                            child: const Text('Farm control'))),
                  TourAnchor(
                      id: 'second',
                      child: TextButton(
                          onPressed: () {},
                          child: const Text('Second control'))),
                ])),
          )),
    );
Future<void> ready(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 850));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 50));
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  test('progress is isolated between owners and survives reopening', () async {
    final prefs = await SharedPreferences.getInstance();
    final a = TourProgress(prefs, 'one'), b = TourProgress(prefs, 'two');
    await a.write('chat', 2);
    expect(b.read('chat'), 0);
    expect(TourProgress(prefs, 'one').read('chat'), 2);
    await a.write('chat', -1);
    expect(a.read('chat'), -1);
  });
  testWidgets('first visit, next, skip and replay never activate the anchor',
      (tester) async {
    var clicks = 0;
    await tester.pumpWidget(app(action: () => clicks++));
    await ready(tester);
    expect(find.text('Meet your farm'), findsOneWidget);
    await tester.tap(find.text('Next'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('Your next step'), findsOneWidget);
    await tester.tap(find.text('Skip tour'));
    await tester.pump();
    expect(clicks, 0);
    expect(find.text('Your next step'), findsNothing);
    await tester.tap(find.byTooltip('Take a tour'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('Meet your farm'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('completed tours stay dismissed and another owner starts fresh',
      (tester) async {
    SharedPreferences.setMockInitialValues({'mitra_tour_v1:one:test': -1});
    await tester.pumpWidget(app());
    await ready(tester);
    expect(find.text('Meet your farm'), findsNothing);
    await tester.pumpWidget(app(owner: 'two'));
    await ready(tester);
    expect(find.text('Meet your farm'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('resumes an interrupted tour and skips an unavailable anchor',
      (tester) async {
    SharedPreferences.setMockInitialValues({'mitra_tour_v1:one:test': 1});
    await tester.pumpWidget(app());
    await ready(tester);
    expect(find.text('Your next step'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(app(missing: true));
    await ready(tester);
    expect(find.text('Finding your next stop…'), findsOneWidget);
    await tester.pump(const Duration(seconds: 5));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(find.text('Your next step'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('phone layout and large text keep controls reachable',
      (tester) async {
    tester.view.physicalSize = const Size(360, 640);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(app(scale: 1.5));
    await ready(tester);
    expect(tester.takeException(), isNull);
    await tester.ensureVisible(find.text('Skip tour'));
    await tester.tap(find.text('Skip tour'));
    await tester.pump();
    expect(find.text('Meet your farm'), findsNothing);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('does not interrupt a modal opened before the automatic tour',
      (tester) async {
    await tester.pumpWidget(app());
    await tester.pump();
    final context = tester.element(find.text('Farm control'));
    showDialog<void>(
        context: context,
        builder: (_) => const AlertDialog(title: Text('Review your edits')));
    await ready(tester);
    expect(find.text('Meet your farm'), findsNothing);
    await tester.pumpWidget(const SizedBox());
  });
  test('coachmark flips above a bottom control and stays inside safe edges',
      () {
    final rect = tourCardRect(
        const Rect.fromLTWH(330, 700, 40, 48),
        const Size(340, 280),
        const Size(390, 844),
        const EdgeInsets.only(top: 24, bottom: 24));
    expect(rect.left, 38);
    expect(rect.bottom, 684);
    expect(rect.right, lessThanOrEqualTo(378));
  });
  testWidgets('Android back dismisses the tour without leaving the page',
      (tester) async {
    await tester.pumpWidget(app());
    await ready(tester);
    await tester.binding.handlePopRoute();
    await tester.pump();
    expect(find.text('Meet your farm'), findsNothing);
    expect(find.text('Farm control'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets(
      'backgrounding removes the overlay and keeps interrupted progress',
      (tester) async {
    await tester.pumpWidget(app());
    await ready(tester);
    await tester.tap(find.text('Next'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump();
    expect(find.text('Your next step'), findsNothing);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pumpWidget(const SizedBox());
    await tester.pump();
    await tester.pumpWidget(app());
    await ready(tester);
    expect(find.text('Your next step'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets(
      'onboarding waits for its restored setup step before showing a guide',
      (tester) async {
    await tester.pumpWidget(const MaterialApp(
        home: TourHost(
            owner: 'one',
            scope: 'onboarding',
            steps: stops,
            child: Scaffold(body: Text('Restoring setup')))));
    await ready(tester);
    expect(find.text('Finding your next stop…'), findsNothing);
    await tester.pumpWidget(const MaterialApp(
        home: TourHost(
            owner: 'one',
            scope: 'onboarding',
            steps: stops,
            child: TourSection(
                scope: 'onboarding-0',
                child: Scaffold(
                    body: TourAnchor(
                        id: 'read', child: Text('Read this to me')))))));
    await ready(tester);
    expect(find.text('We can take this slowly'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });
}
