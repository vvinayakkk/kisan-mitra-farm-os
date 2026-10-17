import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api.dart';
import 'offline.dart';
import 'phone_auth.dart';

/// Backend lane reported by `GET /`. Only the canonical lanes are supported.
enum BackendMode { demo, live, unsupported, unknown }

BackendMode parseMode(Object? value) => switch (value) {
      'v3_demo' => BackendMode.demo,
      'v3_live' => BackendMode.live,
      null => BackendMode.unknown,
      _ => BackendMode.unsupported,
    };

enum AuthStatus { loading, signedOut, signedIn }

class AuthState {
  const AuthState({
    this.status = AuthStatus.loading,
    this.mode = BackendMode.unknown,
    this.session,
    this.error,
    this.busy = false,
    this.codeSent = false,
  });

  final AuthStatus status;
  final BackendMode mode;
  final SessionCapability? session;
  final String? error;
  final bool busy;
  final bool codeSent;

  bool get isAuthenticated => status == AuthStatus.signedIn && session != null;

  AuthState copyWith({
    AuthStatus? status,
    BackendMode? mode,
    SessionCapability? session,
    bool clearSession = false,
    String? error,
    bool clearError = false,
    bool? busy,
    bool? codeSent,
  }) =>
      AuthState(
        status: status ?? this.status,
        mode: mode ?? this.mode,
        session: clearSession ? null : session ?? this.session,
        error: clearError ? null : error ?? this.error,
        busy: busy ?? this.busy,
        codeSent: codeSent ?? this.codeSent,
      );
}

/// Persists only the server-issued capability, in the platform keystore.
class SessionVault {
  SessionVault([FlutterSecureStorage? storage])
      : _storage = storage ?? const FlutterSecureStorage();

  static const _key = 'kisan_mitra_session_v1';
  final FlutterSecureStorage _storage;

  Future<SessionCapability?> read() async {
    try {
      final raw = await _storage.read(key: _key);
      return raw == null ? null : SessionCapability.tryParse(jsonDecode(raw));
    } catch (_) {
      await clear();
      return null;
    }
  }

  Future<void> write(SessionCapability session) =>
      _storage.write(key: _key, value: jsonEncode(session.toJson()));

  Future<void> clear() => _storage.deleteAll();
}

class AuthController extends StateNotifier<AuthState> {
  AuthController(this._vault, {ApiClient Function()? anonymous, PhoneIdentityProvider? phoneIdentity})
      : _anonymous = anonymous ?? (() => ApiClient()),
        _phoneIdentity = phoneIdentity,
        super(const AuthState()) {
    _restore();
  }

  final SessionVault _vault;
  final ApiClient Function() _anonymous;
  PhoneIdentityProvider? _phoneIdentity;
  String? _verificationId;

  PhoneIdentityProvider get phoneIdentity =>
      _phoneIdentity ??= FirebasePhoneIdentity();

  Future<BackendMode> _detectMode() async {
    final api = _anonymous();
    try {
      final root = await api.get('/', timeout: const Duration(seconds: 8));
      return parseMode(root is Map ? root['data_mode'] : null);
    } finally {
      api.close();
    }
  }

  Future<void> _restore() async {
    final stored = await _vault.read();
    var mode = BackendMode.unknown;
    String? error;
    try {
      mode = await _detectMode();
    } on ApiException catch (e) {
      error = e.message;
    }
    // A stored capability is only a candidate: the first private request
    // verifies it and [expire] signs out if the server rejects it.
    state = AuthState(
      status: stored == null ? AuthStatus.signedOut : AuthStatus.signedIn,
      mode: mode,
      session: stored,
      error: stored == null ? error : null,
    );
  }

  Future<void> refreshMode() async {
    state = state.copyWith(busy: true, clearError: true);
    try {
      state = state.copyWith(mode: await _detectMode(), busy: false);
    } on ApiException catch (e) {
      state = state.copyWith(busy: false, error: e.message);
    }
  }

  Future<void> _adopt(SessionCapability session) async {
    await _vault.write(session);
    state = AuthState(status: AuthStatus.signedIn, mode: state.mode, session: session);
  }

  /// Local demo lane only: the backend issues an explicit demo challenge and
  /// rejects this path in live mode. No SMS is sent.
  Future<void> signInDemo({String phone = '9999999999'}) async {
    if (state.mode != BackendMode.demo) {
      state = state.copyWith(error: 'Demo sign-in is only available on a demo server.');
      return;
    }
    state = state.copyWith(busy: true, clearError: true);
    final api = _anonymous();
    try {
      final challenge = await api.post('/api/auth/send-otp', body: {'phone': phone});
      final otp = challenge is Map ? challenge['otp'] : null;
      if (challenge is! Map || challenge['demo_bypass'] != true || otp is! String) {
        throw ApiException(503, 'This server did not issue a demo challenge.');
      }
      final verified = await api.post('/api/auth/verify-otp', body: {'phone': phone, 'otp': otp});
      final session = SessionCapability.tryParse(
          verified is Map ? (verified['session'] ?? verified) : null);
      if (session == null) throw ApiException(502, 'The server returned no workspace session.');
      await _adopt(session);
    } on ApiException catch (e) {
      state = state.copyWith(busy: false, error: e.message);
    } finally {
      api.close();
    }
  }

  Future<void> _finishPhoneSignIn(String token) async {
    final api = _anonymous();
    try {
      final created = await api.post('/api/assistant/sessions',
          extraHeaders: {'Authorization': 'Bearer $token'});
      final session = SessionCapability.tryParse(created);
      if (session == null) throw ApiException(502, 'The server returned no workspace session.');
      await _adopt(session);
    } on ApiException catch (e) {
      state = state.copyWith(busy: false, error: e.message);
    } catch (_) {
      state = state.copyWith(busy: false, error: 'Sign-in could not finish. Please retry.');
    } finally {
      api.close();
    }
  }

  Future<void> sendPhoneCode(String phone) async {
    if (state.mode != BackendMode.live) {
      state = state.copyWith(error: 'Phone sign-in needs the live farm service.');
      return;
    }
    final normalized = phone.replaceAll(RegExp(r'[\s-]'), '');
    if (!RegExp(r'^\+91[6-9]\d{9}$').hasMatch(normalized)) {
      state = state.copyWith(error: 'Enter a valid Indian number with +91.');
      return;
    }
    _verificationId = null;
    state = state.copyWith(busy: true, codeSent: false, clearError: true);
    try {
      await phoneIdentity.sendCode(
        normalized,
        onCodeSent: (id) {
          _verificationId = id;
          state = state.copyWith(busy: false, codeSent: true);
        },
        onVerified: (token) => _finishPhoneSignIn(token),
        onError: (message) => state = state.copyWith(busy: false, error: message),
      );
    } catch (_) {
      state = state.copyWith(busy: false, error: 'Could not send the code. Please retry.');
    }
  }

  Future<void> confirmPhoneCode(String code) async {
    final verificationId = _verificationId;
    if (verificationId == null || !RegExp(r'^\d{6}$').hasMatch(code)) {
      state = state.copyWith(error: 'Enter the six-digit code.');
      return;
    }
    state = state.copyWith(busy: true, clearError: true);
    try {
      await _finishPhoneSignIn(await phoneIdentity.confirmCode(verificationId, code));
    } catch (_) {
      state = state.copyWith(busy: false, error: 'The code could not be verified. Try again.');
    }
  }

  /// Server rejected the capability (revoked, expired, other device signed out).
  Future<void> expire() async {
    if (state.session == null) return;
    await _vault.clear();
    if (state.mode == BackendMode.live) await phoneIdentity.signOut();
    await OfflineStore.clearAll();
    state = AuthState(
        status: AuthStatus.signedOut,
        mode: state.mode,
        error: 'Your session ended. Please sign in again.');
  }

  /// Revokes server-side (history is preserved) then wipes local secrets.
  Future<void> signOut() async {
    final session = state.session;
    if (session != null) {
      final api = ApiClient(session: session);
      try {
        await api.post('/api/assistant/sessions/${session.id}/revoke',
            timeout: const Duration(seconds: 4));
      } catch (_) {
        // Local sign-out proceeds; the capability is erased from this device.
      } finally {
        api.close();
      }
    }
    await _vault.clear();
    if (state.mode == BackendMode.live) await phoneIdentity.signOut();
    await OfflineStore.clearAll();
    state = AuthState(status: AuthStatus.signedOut, mode: state.mode);
  }
}

final sessionVaultProvider = Provider<SessionVault>((_) => SessionVault());

final authProvider = StateNotifierProvider<AuthController, AuthState>(
  (ref) => AuthController(ref.read(sessionVaultProvider)),
);

/// Saved copies belong to one session; a new sign-in starts empty.
final offlineStoreProvider = Provider<OfflineStore?>((ref) {
  final id = ref.watch(authProvider.select((s) => s.session?.id));
  return id == null ? null : OfflineStore(id);
});

/// API client bound to the current session. Rebuilt (and the old one closed)
/// whenever the session changes, so stale responses cannot cross accounts.
final apiProvider = Provider<ApiClient>((ref) {
  final session = ref.watch(authProvider.select((s) => s.session));
  final api = ApiClient(session: session, offline: session == null ? null : ref.watch(offlineStoreProvider));
  api.onUnauthorized = () => ref.read(authProvider.notifier).expire();
  ref.onDispose(api.close);
  return api;
});
