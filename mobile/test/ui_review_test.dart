import 'dart:convert';
import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:easy_localization/easy_localization.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:skyview_app/core/api.dart';
import 'package:skyview_app/core/session.dart';
import 'package:skyview_app/core/offline.dart';
import 'package:skyview_app/ui/offline_banner.dart';
import 'package:skyview_app/assistant/assistant_controller.dart';
import 'package:skyview_app/assistant/models.dart';
import 'package:skyview_app/assistant/chat_screen.dart';
import 'package:skyview_app/screens/choice_screen.dart';
import 'package:skyview_app/screens/onboarding_screen.dart';
import 'package:skyview_app/screens/splash_screen.dart';
import 'package:skyview_app/features/profile_screen.dart';
import 'package:skyview_app/features/weather_screen.dart';
import 'package:skyview_app/features/station_screen.dart';
import 'package:skyview_app/features/calendar_screen.dart';
import 'package:skyview_app/features/crop_doctor_screen.dart';
import 'package:skyview_app/features/schemes_screen.dart';
import 'package:skyview_app/features/markets_screen.dart';
import 'package:skyview_app/features/saathi.dart';
import 'package:skyview_app/features/notebook/notebook_screen.dart';
import 'package:skyview_app/features/exchange/exchange_screen.dart';
import 'package:skyview_app/voice/live_voice.dart';
import 'package:skyview_app/voice/speech.dart';
import 'package:skyview_app/utils/constants.dart';
import 'auth_controller_test.dart' show MemoryVault;
import 'l10n.dart';

final Map<String,dynamic> _database = const String.fromEnvironment('REVIEW_DATA').isEmpty ? {} : jsonDecode(File(const String.fromEnvironment('REVIEW_DATA')).readAsStringSync());

const _sid = '0123456789abcdef0123456789abcdef';
const _session = SessionCapability(id: _sid, token: 'local-test-fixture');
const _profile = {
  'name': 'Aarav Patel',
  'location': 'Nashik',
  'state': 'Maharashtra',
  'district': 'Nashik',
  'land_size_acres': 4.5,
  'mapped_plot_area_acres': 4.5,
  'crops': ['Onion', 'Tomato'],
  'latitude': 20.0,
  'longitude': 73.8,
  'preferred_language': 'en',
  'excess_resources': ['Water pump'],
  'required_resources': []
};

class _Assets extends AssetLoader {
  const _Assets();
  @override
  Future<Map<String, dynamic>> load(String path, Locale locale) async =>
      jsonDecode(File('assets/translations/en.json').readAsStringSync());
}

class _Assistant extends AssistantController {
  _Assistant([String scenario = '']) : super(ApiClient(), () => 'en', () {}) {
    state = const AssistantState(ready: true, messages: [
      ChatMessage(
          id: 'u1',
          role: Role.user,
          text: 'What should I focus on this morning?'),
      ChatMessage(
          id: 'a1',
          role: Role.assistant,
          status: 'completed',
          text:
              'Let’s keep today simple.\n\nStart with a short walk through your onion field. Look at the leaves and note any changes since yesterday.\n\nI can help you turn your observations into a plan.',
          activities: [
            Activity(
                callId: 'c1',
                tool: 'list_tasks',
                label: 'Checked your saved farm tasks',
                status: ActivityStatus.done,
                elapsedMs: 230)
          ]),
    ], conversations: [
      Conversation(
          id: 'archive1',
          title: 'Planning the next onion crop',
          createdAt: '2026-10-16T09:00:00Z')
    ]);
    if (_database.isNotEmpty) {
      final snapshot = SessionSnapshot.fromJson(_database['/api/assistant/session']);
      state = state.copyWith(tasks: snapshot.tasks, conversations: snapshot.conversations);
    }
    if (scenario.startsWith('15-') || scenario.startsWith('16-') || scenario.startsWith('17-')) {
      state = state.copyWith(outbox: ['Help me plan tomorrow’s field work'], syncing: scenario.startsWith('16-'), outboxNeedsReview: scenario.startsWith('17-'));
    }
    if (scenario == '04a-chat-working') {
      state = state.copyWith(running: true, messages: [state.messages.first,
        const ChatMessage(id: 'a2', role: Role.assistant, status: 'working', activities: [
          Activity(callId: 'weather', tool: 'weather_forecast', label: 'Checking your local forecast', status: ActivityStatus.running),
        ])]);
    }
    if (scenario == '04b-chat-question') {
      state = state.copyWith(pending: Pending.fromJson({'id': 'q1', 'kind': 'question', 'tool': 'ask_farmer',
        'arguments': {'question': 'How do you water this field?', 'fields': [
          {'id': 'water', 'label': 'Irrigation method', 'type': 'select', 'options': ['Rainfed', 'Drip', 'Sprinkler']}
        ]}}));
    }
  }
}

class _Speech extends SpeechService {
  _Speech() : super(ApiClient());
  @override
  void dispose() {}
  @override
  Future<void> start() async {}
  @override
  Stream<double> levels() => const Stream.empty();
  @override
  Future<void> cancel() async {}
  @override
  Future<void> stopSpeaking() async {}
}

Object _response(http.Request r) {
  final p = r.url.path;
  if (_database.isNotEmpty) {
    final tool = p.contains('/inspect/') ? p.split('/').last : null;
    if (tool != null && _database.containsKey('inspect:$tool')) return _database['inspect:$tool'];
    final exact = p + (r.url.hasQuery ? '?${r.url.query}' : '');
    if (_database.containsKey(exact)) return _database[exact];
    if (_database.containsKey(p)) return _database[p];
    if (p == '/api/exchange/listings') return _database['/api/exchange/listings?mine=false&kind=&category=&q='] ?? {'items': []};
  }
  if (p == '/') return {'data_mode': 'v3_demo'};
  if (p == '/api/profile') return {'profile': _profile};
  if (p == '/api/onboarding/options') {
    return {
      'regions': [
        {'id': 'state1', 'name': 'Maharashtra'}
      ],
      'crops': []
    };
  }
  if (p == '/api/weather/dashboard') {
    return {
      'available': true,
      'live': {
        'source': 'Local visual fixture',
        'captured_at': '2026-10-17T08:00:00Z',
        'current': {
          'temperature_2m': 26,
          'relative_humidity_2m': 68,
          'weather_code': 2,
          'wind_speed_10m': 9,
          'apparent_temperature': 27
        },
        'daily': {
          'time': ['2026-10-17', '2026-10-18', '2026-10-19'],
          'temperature_2m_min': [20, 21, 20],
          'temperature_2m_max': [28, 29, 27],
          'precipitation_sum': [0, 2, 4],
          'precipitation_probability_max': [10, 30, 60],
          'weather_code': [2, 2, 61]
        },
        'hourly': {},
        'air': {}
      },
      'forecast': {'farm': 'Nashik farm', 'records': []}
    };
  }
  if (p == '/api/sensors/stations') {
    return {
      'stations': [
        {'station_id': 'MY-FIELD'}
      ]
    };
  }
  if (p.startsWith('/api/assistant/station/')) {
    return {
      'available': true,
      'source': 'Field station',
      'station_id': 'MY-FIELD',
      'data': {
        'temperature': 26.2,
        'humidity': 68,
        'soilMoisture': 32.4,
        'soilTemperature': 24.1,
        'rainfall': 0,
        'windSpeed': 9
      },
      'provenance': {'observation_age_seconds': 45}
    };
  }
  if (p == '/api/companion') {
    return {
      'name': 'Saathi',
      'status': 'ready',
      'settings': {
        'enabled': true,
        'frequency_hours': 6,
        'quiet_start': '20:00',
        'quiet_end': '06:00'
      },
      'activity': [],
      'channels': {}
    };
  }
  if (p == '/api/companion/proposals') {
    return {
      'proposals': [],
      'job': {'state': 'done'}
    };
  }
  if (p.contains('scheme_search')) {
    return {
      'schemes': [
        {
          'name': 'PM-KISAN',
          'description':
              'Income support for eligible landholding farmer families.',
          'category': 'Income support',
          'source_url': 'https://pmkisan.gov.in',
          'eligibility': 'Check official eligibility requirements.'
        }
      ]
    };
  }
  if (p.contains('market_prices')) return {'prices': []};
  if (p.contains('market_trend')) return {};
  if (p == '/api/farm-workspace/today') {
    return {
      'actions': [],
      'counts': {'tasks': 0, 'cases': 0, 'missions': 0}
    };
  }
  if (p == '/api/farms') return {'farms': []};
  if (p == '/api/plots') return {'plots': []};
  if (p == '/api/crop-cycles') return {'crop_cycles': []};
  return {
    'items': [],
    'proposals': [],
    'job': {'state': 'done'}
  };
}

String _flutterRoot() {
  final configured = Platform.environment['FLUTTER_ROOT'];
  if (configured != null) return configured;
  var dir = File(Platform.resolvedExecutable).parent;
  while (dir.parent.path != dir.path) {
    if (File(
            '${dir.path}/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf')
        .existsSync()) {
      return dir.path;
    }
    dir = dir.parent;
  }
  throw StateError('Set FLUTTER_ROOT for rendering icon fonts.');
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    loadEnglish();
    await EasyLocalization.ensureInitialized();
    final loader = FontLoader('Poppins');
    for (final weight in ['Regular', 'Medium', 'SemiBold', 'Bold']) {
      loader.addFont(Future.value(ByteData.sublistView(
          File('assets/fonts/Poppins-$weight.ttf').readAsBytesSync())));
    }
    await loader.load();
    final icons = FontLoader('MaterialIcons')
      ..addFont(Future.value(ByteData.sublistView(File(
              '${_flutterRoot()}/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf')
          .readAsBytesSync())));
    await icons.load();
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
            const MethodChannel('plugin.csdcorp.com/speech_to_text'),
            (_) async => false);
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
            const MethodChannel('xyz.luan/audioplayers'), (_) async => 1);
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
            const MethodChannel('xyz.luan/audioplayers.global'),
            (_) async => 1);
  });
  final screens = <String, Widget>{
    '00-splash': const SplashScreen(),
    '02d-onboarding-resumed': const OnboardingScreen(),
    '01-home': const ChoiceScreen(),
    '02-onboarding': const OnboardingScreen(),
    '02a-onboarding-location': const OnboardingScreen(),
    '02b-onboarding-farm': const OnboardingScreen(),
    '02c-onboarding-review': const OnboardingScreen(),
    '03-voice': const LiveVoiceSheet(runContext: RunContext(), maxSeconds: 30),
    '03a-voice-captions': const LiveVoiceSheet(runContext: RunContext(), maxSeconds: 30),
    '04-chat': const ChatScreen(),
    '04a-chat-working': const ChatScreen(),
    '04b-chat-question': const ChatScreen(),
    '05-profile': const ProfileScreen(),
    '06-weather': const WeatherScreen(),
    '07-station': const StationScreen(),
    '08-tasks': const CalendarScreen(),
    '09-crop-doctor': const CropDoctorScreen(),
    '10-notebook': const NotebookScreen(),
    '10a-fields': const NotebookScreen(initialTab: 'fields'),
    '10b-plans': const NotebookScreen(initialTab: 'missions'),
    '11-exchange': const ExchangeScreen(),
    '12-saathi': const SaathiScreen(),
    '13-schemes': const SchemesScreen(),
    '15-offline': const OfflineFrame(child: ChatScreen()),
    '16-syncing': const OfflineFrame(child: ChatScreen()),
    '17-interrupted': const OfflineFrame(child: ChatScreen()),
    '14-markets': const MarketsScreen()
  };
  for (final entry in screens.entries) {
    testWidgets('review ${entry.key}', (tester) async {
      SharedPreferences.setMockInitialValues(entry.key == '02d-onboarding-resumed' ? {
        'onboarding_draft_$_sid': jsonEncode({'step': 2, 'name': 'Ravi', 'place': 'Guntur', 'farm': 'My north field', 'area': '2.5', 'crops': 'Groundnut', 'ownership': 'leased', 'irrigation': 'drip', 'saveRoutines': false})
      } : {});
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(const MethodChannel('plugin.csdcorp.com/speech_to_text'), (call) async {
        if (call.method == 'initialize' || call.method == 'listen') return entry.key == '03a-voice-captions';
        return null;
      });
      tester.view.physicalSize = Size(
          const int.fromEnvironment('REVIEW_WIDTH', defaultValue: 430)
              .toDouble(),
          932);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final slowTrend = Completer<void>();
      final api = ApiClient(
          session: _session,
          client: MockClient(
              (r) async {
                if (const bool.fromEnvironment('TEST_SLOW_TREND') && entry.key == '14-markets' && r.url.path.endsWith('/market_trend')) await slowTrend.future;
                return http.Response(jsonEncode(_response(r)), 200, headers: {'content-type': 'application/json; charset=utf-8'}, request: r);
              }),
          baseUrl: 'http://fixture');
      final key = GlobalKey();
      final app = EasyLocalization(
          supportedLocales: const [Locale('en')],
          path: 'assets/translations',
          assetLoader: const _Assets(),
          child: ProviderScope(
              overrides: [
                apiProvider.overrideWithValue(api),
                authProvider.overrideWith((_) => AuthController(
                    MemoryVault(_session),
                    anonymous: () => ApiClient(
                        client: MockClient((_) async =>
                            http.Response('{"data_mode":"v3_demo"}', 200))))),
                assistantProvider.overrideWith((_) => _Assistant(entry.key)),
                offlineProvider.overrideWith((_) => Stream.value(entry.key == '15-offline')),
                speechProvider.overrideWith((_) => _Speech()),
                speechCapabilitiesProvider.overrideWith((_) async =>
                    const SpeechCapabilities(
                        conversation: true,
                        transcription: true,
                        playback: true,
                        playbackLanguages: {'en-IN'})),
              ],
              child: Builder(
                  builder: (context) => MaterialApp(
                      theme: buildAppTheme(
                          dark: const bool.fromEnvironment('REVIEW_DARK')),
                      builder: (context, child) => MediaQuery(
                          data: MediaQuery.of(context).copyWith(
                              textScaler: TextScaler.linear(
                                  const bool.fromEnvironment(
                                          'REVIEW_LARGE_TEXT')
                                      ? 1.3
                                      : 1)),
                          child: child!),
                      localizationsDelegates: context.localizationDelegates,
                      supportedLocales: context.supportedLocales,
                      locale: context.locale,
                      home: RepaintBoundary(key: key, child: entry.value)))));
      await tester.pumpWidget(app);
      for (var i = 0; i < 12; i++) {
        await tester.pump(const Duration(milliseconds: 100));
        if (entry.key == '00-splash' && const bool.fromEnvironment('CAPTURE_REVIEW')) {
          await tester.runAsync(() async {
            final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
            final frame = await boundary.toImage(pixelRatio: 1);
            final bytes = await frame.toByteData(format: ui.ImageByteFormat.png);
            final dir = Directory('${const String.fromEnvironment('REVIEW_OUTPUT', defaultValue: 'work/ui-review')}/motion');
            await dir.create(recursive: true);
            await File('${dir.path}/frame-${i.toString().padLeft(2,'0')}.png').writeAsBytes(bytes!.buffer.asUint8List());
          });
        }
      }
      if (entry.key == '02d-onboarding-resumed') {
        expect(find.text('My north field'), findsOneWidget);
        expect(find.text('Let’s meet your farm.'), findsOneWidget);
        expect(find.text('leased'), findsWidgets);
        await tester.enterText(find.widgetWithText(TextField, 'My north field'), 'My riverside field');
        await tester.pump(const Duration(milliseconds: 100));
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump(const Duration(milliseconds: 100));
        await tester.pumpWidget(app);
        for (var i=0;i<12;i++) { await tester.pump(const Duration(milliseconds: 100)); }
        expect(find.text('My riverside field'), findsOneWidget);
        expect(find.text('Let’s meet your farm.'), findsOneWidget);
        expect(find.text('Groundnut'), findsOneWidget);
      }
      if (entry.key == '03a-voice-captions') {
        Future<void> partial(String words) async {
          final data = const StandardMethodCodec().encodeMethodCall(MethodCall('textRecognition', jsonEncode({'alternates': [{'recognizedWords': words, 'confidence': 0.9}], 'resultType': 0})));
          await tester.binding.defaultBinaryMessenger.handlePlatformMessage('plugin.csdcorp.com/speech_to_text', data, (_) {});
          await tester.pump();
          await tester.pump(const Duration(milliseconds: 300));
        }
        await partial('Help me plan');
        expect(find.text('“Help me plan”'), findsOneWidget);
        await partial('Help me plan my farm work for tomorrow');
        expect(find.text('“Help me plan my farm work for tomorrow”'), findsOneWidget);
      }
      expect(find.textContaining(RegExp(r'\bdemo\b', caseSensitive: false)), findsNothing);
      final onboardingStep = {'02a-onboarding-location': 1, '02b-onboarding-farm': 2, '02c-onboarding-review': 3}[entry.key] ?? 0;
      for (var step = 0; step < onboardingStep; step++) {
        await tester.tap(find.text('Continue'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 350));
        await tester.pump();
      }
      if (entry.key == '04a-chat-working') {
        await tester.enterText(find.byType(TextField).last, 'Also help me plan tomorrow');
        expect(find.text('Also help me plan tomorrow'), findsOneWidget);
        await tester.pump();
      }
      expect(tester.takeException(), isNull);
      if (const bool.fromEnvironment('CHECK_A11Y')) {
        final semantics = tester.ensureSemantics();
        await tester.pump();
        await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
        await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
        semantics.dispose();
      }
      if (const bool.fromEnvironment('TEST_SLOW_TREND') && entry.key == '14-markets') {
        expect(find.text('Compare what I take home'), findsOneWidget);
        expect(slowTrend.isCompleted, isFalse);
        slowTrend.complete();
        await tester.pump();
      }
      if (const bool.fromEnvironment('CHECK_CONTRAST')) {
        final semantics = tester.ensureSemantics(); await tester.pump();
        await expectLater(tester, meetsGuideline(textContrastGuideline));
        semantics.dispose();
      }
      if (const bool.fromEnvironment('CAPTURE_REVIEW')) {
        final boundary =
            key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
        await tester.runAsync(() async {
          final image = await boundary.toImage(pixelRatio: 2);
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          final dir = Directory(const String.fromEnvironment('REVIEW_OUTPUT',
              defaultValue: 'work/ui-review'));
          await dir.create(recursive: true);
          await File('${dir.path}/${entry.key}.png')
              .writeAsBytes(bytes!.buffer.asUint8List());
        });
      }
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump(const Duration(seconds: 1));
    });
  }
}
