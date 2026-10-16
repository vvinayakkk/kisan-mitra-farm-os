import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:skyview_app/core/api.dart';
import 'package:skyview_app/core/session.dart';

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

ApiClient Function() server(String mode, {bool demoChallenge = true}) => () => ApiClient(
      baseUrl: 'http://t',
      client: MockClient((r) async {
        switch (r.url.path) {
          case '/':
            return http.Response(jsonEncode({'data_mode': mode}), 200);
          case '/api/auth/send-otp':
            return demoChallenge
                ? http.Response(jsonEncode({'status': 'success', 'demo_bypass': true, 'otp': '999999'}), 200)
                : http.Response('{"detail":"Real OTP login needs a configured verification provider."}', 503);
          case '/api/auth/verify-otp':
            expect(jsonDecode(r.body)['otp'], '999999');
            return http.Response(jsonEncode({'status': 'success', 'session': {'id': 'e' * 32, 'token': 'tok'}}), 200);
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
    expect(c.state.error, contains('demo server'));
  });

  test('live sign-in fails closed when the build has no OIDC provider', () async {
    final c = AuthController(MemoryVault(), anonymous: server('v3_live'));
    await settle(c);
    await c.signInLive();
    expect(c.state.isAuthenticated, isFalse);
    expect(c.state.error, contains('not configured'));
  });

  test('server refusal of the demo challenge is shown, not bypassed', () async {
    final c = AuthController(MemoryVault(), anonymous: server('v3_demo', demoChallenge: false));
    await settle(c);
    await c.signInDemo();
    expect(c.state.isAuthenticated, isFalse);
    expect(c.state.error, contains('verification provider'));
  });

  test('an expired capability is erased and the farmer is signed out', () async {
    final vault = MemoryVault(const SessionCapability(id: 'f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0', token: 'old'));
    final c = AuthController(vault, anonymous: server('v3_demo'));
    await settle(c);
    expect(c.state.isAuthenticated, isTrue);
    await c.expire();
    expect(c.state.isAuthenticated, isFalse);
    expect(vault.value, isNull);
  });
}
