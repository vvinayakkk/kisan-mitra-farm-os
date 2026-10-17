import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:skyview_app/core/api.dart';
import 'package:skyview_app/core/session.dart';
import 'package:skyview_app/core/phone_auth.dart';

import 'l10n.dart';

class MemoryVault extends SessionVault {
  MemoryVault([this.value]);

  SessionCapability? value;

  @override
  Future<SessionCapability?> read() async => value;

  @override
  Future<void> write(SessionCapability session) async => value = session;

  @override
  Future<void> clear() async => value = null;
}

class TestPhoneIdentity implements PhoneIdentityProvider {
  String? sentTo;
  String? restored;
  @override
  Future<String?> restoredToken() async => restored;

  @override
  Future<void> sendCode(String phone,
      {required void Function(String) onCodeSent,
      required Future<void> Function(String) onVerified,
      required void Function(String) onError}) async {
    sentTo = phone;
    onCodeSent('verification-1');
  }

  @override
  Future<String> confirmCode(String verificationId, String code) async {
    expect(verificationId, 'verification-1');
    expect(code, '436281');
    return 'firebase-id-token';
  }

  @override
  Future<void> signOut() async {}
}

ApiClient Function() server(String mode, {bool demoChallenge = true}) =>
    () => ApiClient(
          baseUrl: 'http://t',
          client: MockClient((r) async {
            switch (r.url.path) {
              case '/':
                return http.Response(jsonEncode({'data_mode': mode}), 200);
              case '/api/auth/send-otp':
                return demoChallenge
                    ? http.Response(
                        jsonEncode({
                          'status': 'success',
                          'demo_bypass': true,
                          'otp': '999999'
                        }),
                        200)
                    : http.Response(
                        '{"detail":"Real OTP login needs a configured verification provider."}',
                        503);
              case '/api/auth/verify-otp':
                expect(jsonDecode(r.body)['otp'], '999999');
                return http.Response(
                    jsonEncode({
                      'status': 'success',
                      'session': {'id': 'e' * 32, 'token': 'tok'}
                    }),
                    200);
              case '/api/assistant/sessions':
                expect(r.headers['authorization'], 'Bearer firebase-id-token');
                return http.Response(
                    jsonEncode({'id': 'e' * 32, 'token': 'tok'}), 200);
            }
            return http.Response('{}', 404);
          }),
        );

Future<void> settle(AuthController c) async {
  for (var i = 0; i < 50 && c.state.status == AuthStatus.loading; i++) {
    await Future<void>.delayed(const Duration(milliseconds: 5));
  }
}

void main() {
  setUpAll(loadEnglish);

  test('demo lane adopts the server-issued session', () async {
    final vault = MemoryVault();
    final c = AuthController(vault, anonymous: server('v3_demo'));
    await settle(c);
    expect(c.state.mode, BackendMode.demo);
    await c.signInDemo();
    expect(c.state.isAuthenticated, isTrue);
    expect(vault.value?.id, 'e' * 32);
  });

  test('demo sign-in is refused on a live server', () async {
    final c = AuthController(MemoryVault(), anonymous: server('v3_live'));
    await settle(c);
    await c.signInDemo();
    expect(c.state.isAuthenticated, isFalse);
    expect(c.state.error, contains('Use phone sign-in'));
  });

  test('live phone code is verified before the backend issues a session',
      () async {
    final identity = TestPhoneIdentity();
    final c = AuthController(MemoryVault(),
        anonymous: server('v3_live'), phoneIdentity: identity);
    await settle(c);
    await c.sendPhoneCode('+919999999999');
    expect(identity.sentTo, '+919999999999');
    expect(c.state.codeSent, isTrue);
    await c.confirmPhoneCode('436281');
    expect(c.state.isAuthenticated, isTrue);
  });

  test('server refusal of the demo challenge is shown, not bypassed', () async {
    final c = AuthController(MemoryVault(),
        anonymous: server('v3_demo', demoChallenge: false));
    await settle(c);
    await c.signInDemo();
    expect(c.state.isAuthenticated, isFalse);
    expect(c.state.error, contains('verification provider'));
  });

  test('an expired capability is erased and the farmer is signed out',
      () async {
    final vault = MemoryVault(const SessionCapability(
        id: 'f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0', token: 'old'));
    final c = AuthController(vault, anonymous: server('v3_demo'));
    await settle(c);
    expect(c.state.isAuthenticated, isTrue);
    await c.expire();
    expect(c.state.isAuthenticated, isFalse);
    expect(vault.value, isNull);
  });
  test(
      'live session expiry silently renews with the remembered Firebase identity',
      () async {
    final identity = TestPhoneIdentity()..restored = 'firebase-id-token';
    final vault = MemoryVault(const SessionCapability(
        id: 'ffffffffffffffffffffffffffffffff', token: 'old'));
    final c = AuthController(vault,
        anonymous: server('v3_live'), phoneIdentity: identity);
    await Future<void>.delayed(const Duration(milliseconds: 20));
    await Future.wait([c.expire(), c.expire()]);
    expect(c.state.isAuthenticated, isTrue);
    expect(vault.value?.token, 'tok');
    c.dispose();
  });

  test('restores Firebase identity when the app capability is missing',
      () async {
    final identity = TestPhoneIdentity()..restored = 'firebase-id-token';
    final c = AuthController(MemoryVault(),
        anonymous: server('v3_live'), phoneIdentity: identity);
    await settle(c);
    expect(c.state.isAuthenticated, isTrue);
    expect(identity.sentTo, isNull);
    c.dispose();
  });
}
