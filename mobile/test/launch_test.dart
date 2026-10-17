import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:skyview_app/core/onboarding_progress.dart';
import 'package:skyview_app/core/launch.dart';
import 'package:skyview_app/core/api.dart';
import 'package:skyview_app/core/session.dart';
import 'auth_controller_test.dart' show MemoryVault;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const session =
      SessionCapability(id: '0123456789abcdef0123456789abcdef', token: 'test');
  const complete = {
    'name': 'Ravi',
    'state': 'AP',
    'crops': ['Groundnut'],
    'land_size_acres': 2
  };
  setUp(() => SharedPreferences.setMockInitialValues({}));
  test(
      'partial form survives reopening, skip retains it, completion removes it',
      () async {
    final prefs = await SharedPreferences.getInstance();
    await OnboardingProgress(prefs, 'a')
        .write({'step': 2, 'farm': 'Riverside', 'area': '2.5'});
    final reopened = OnboardingProgress(prefs, 'a');
    expect(reopened.read()?['step'], 2);
    expect(reopened.read()?['farm'], 'Riverside');
    expect(OnboardingProgress(prefs, 'b').read(), isNull);
    await reopened.leave(completed: false);
    expect(
        destinationForProfile({},
            dismissed: reopened.dismissed, hasDraft: true),
        '/');
    expect(reopened.read(), isNotNull);
    await reopened.leave(completed: true);
    expect(reopened.read(), isNull);
  });
  test('silent session renewal carries the draft to the renewed session only',
      () async {
    final prefs = await SharedPreferences.getInstance();
    final progress = OnboardingProgress(prefs, 'old');
    await progress.write({'step': 2, 'farm': 'Riverside'});
    await progress.leave(completed: false);
    await progress.transferTo('renewed');
    expect(progress.read(), isNull);
    expect(OnboardingProgress(prefs, 'renewed').read()?['step'], 2);
    expect(OnboardingProgress(prefs, 'renewed').dismissed, isTrue);
    expect(OnboardingProgress(prefs, 'other').read(), isNull);
  });
  test(
      'complete profile opens farm; incomplete profile or active draft resumes setup',
      () {
    expect(destinationForProfile(complete, dismissed: false, hasDraft: false),
        '/');
    expect(destinationForProfile({}, dismissed: false, hasDraft: false),
        '/onboarding');
    expect(destinationForProfile(complete, dismissed: false, hasDraft: true),
        '/onboarding');
  });
  Future<String> launch(
      {bool signedIn = true,
      bool offline = false,
      Map<String, dynamic> profile = complete}) async {
    final container = ProviderContainer(overrides: [
      authProvider.overrideWith((_) => AuthController(
          MemoryVault(signedIn ? session : null),
          anonymous: () => ApiClient(
              client: MockClient((_) async =>
                  http.Response('{"data_mode":"v3_demo"}', 200))))),
      apiProvider.overrideWithValue(ApiClient(
          session: session,
          client: MockClient((_) async {
            if (offline) throw const ApiExceptionForTest();
            return http.Response(jsonEncode({'profile': profile}), 200);
          }))),
    ]);
    addTearDown(container.dispose);
    container.read(authProvider);
    for (var i = 0; i < 10; i++) {
      await Future<void>.delayed(Duration.zero);
    }
    return container.read(launchDestinationProvider.future);
  }

  test('returning signed-in user goes directly to farm', () async {
    expect(await launch(), '/');
  });
  test('unfinished draft resumes even when network is unavailable', () async {
    final prefs = await SharedPreferences.getInstance();
    await OnboardingProgress(prefs, session.id).write({'step': 2});
    expect(await launch(offline: true), '/onboarding');
  });
  test('offline returning user is not trapped on splash', () async {
    expect(await launch(offline: true), '/');
  });
  test(
      'new signed-out user selects language; returning signed-out user signs in',
      () async {
    expect(await launch(signedIn: false), '/language_select');
    await (await SharedPreferences.getInstance())
        .setBool('has_signed_in', true);
    expect(await launch(signedIn: false), '/login');
  });
}

class ApiExceptionForTest implements Exception {
  const ApiExceptionForTest();
}
