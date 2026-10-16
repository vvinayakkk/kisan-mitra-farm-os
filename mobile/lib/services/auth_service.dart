import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

import '../utils/constants.dart';

class AuthState {
  final bool isAuthenticated;
  final String? phone;
  final String? token;

  const AuthState({
    this.isAuthenticated = false,
    this.phone,
    this.token,
  });

  AuthState copyWith({bool? isAuthenticated, String? phone, String? token}) {
    return AuthState(
      isAuthenticated: isAuthenticated ?? this.isAuthenticated,
      phone: phone ?? this.phone,
      token: token ?? this.token,
    );
  }
}

class AuthNotifier extends StateNotifier<AuthState> {
  final FlutterSecureStorage _storage;

  AuthNotifier(this._storage) : super(const AuthState()) {
    _init();
  }

  Future<void> _init() async {
    final token = await _storage.read(key: kTokenKey);
    final phone = await _storage.read(key: kPhoneKey);
    if (token != null && phone != null) {
      state = AuthState(isAuthenticated: true, phone: phone, token: token);
    }
  }

  Future<Map<String, dynamic>> sendOtp(String phone,
      {bool isSignup = false}) async {
    try {
      final res = await http.post(
        Uri.parse('$kBaseUrl/api/auth/send-otp'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'phone': phone, 'is_signup': isSignup}),
      );
      final data = jsonDecode(res.body) as Map<String, dynamic>;

      if (res.statusCode == 200 && data['status'] == 'success') {

        return {'success': true, 'otp': data['otp']};
      }
      return {
        'success': false,
        'message': data['detail'] ?? 'Failed to send OTP.',
      };
    } catch (e) {
      return {'success': false, 'message': 'Network error: $e'};
    }
  }

  Future<bool> verifyOtp(String phone, String otp) async {
    try {
      final res = await http.post(
        Uri.parse('$kBaseUrl/api/auth/verify-otp'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'phone': phone, 'otp': otp}),
      );
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        if (data['status'] == 'success') {
          final token = data['token'] as String;
          await _storage.write(key: kTokenKey, value: token);
          await _storage.write(key: kPhoneKey, value: phone);
          state = AuthState(
              isAuthenticated: true, phone: phone, token: token);
          return true;
        }
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  Future<bool> saveProfile({
    required String phone,
    required String name,
    required double landSize,
    required String location,
    required List<String> crops,
  }) async {
    try {
      final res = await http.post(
        Uri.parse('$kBaseUrl/api/profile/save'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'phone': phone,
          'name': name,
          'land_size_acres': landSize,
          'location': location,
          'crops': crops,
        }),
      );
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body) as Map<String, dynamic>;
        return data['status'] == 'success';
      }
      return false;
    } catch (_) {
      return false;
    }
  }

  Future<void> logout() async {
    await _storage.deleteAll();
    state = const AuthState();
  }
}

final _secureStorageProvider =
    Provider<FlutterSecureStorage>((_) => const FlutterSecureStorage());

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>(
  (ref) => AuthNotifier(ref.read(_secureStorageProvider)),
);
