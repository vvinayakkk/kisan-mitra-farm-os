import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

/// Local, session-scoped unfinished form. It is never a submitted farm profile.
class OnboardingProgress {
  OnboardingProgress(this.prefs, this.sessionId);
  final SharedPreferences prefs;
  final String sessionId;
  String get key => 'onboarding_draft_$sessionId';
  bool get dismissed => prefs.getBool('onboarding_seen_$sessionId') ?? false;
  Map<String, dynamic>? read() {
    try {
      final raw = prefs.getString(key);
      return raw == null ? null : Map<String, dynamic>.from(jsonDecode(raw));
    } catch (_) {
      return null;
    }
  }

  Future<void> write(Map<String, dynamic> value) async {
    await prefs.setString(key, jsonEncode(value));
  }

  Future<void> transferTo(String renewedSessionId) async {
    final next = OnboardingProgress(prefs, renewedSessionId);
    final draft = read();
    if (draft != null) await next.write(draft);
    if (dismissed) {
      await prefs.setBool('onboarding_seen_$renewedSessionId', true);
    }
    await prefs.remove(key);
    await prefs.remove('onboarding_seen_$sessionId');
  }

  Future<void> leave({required bool completed}) async {
    await prefs.setBool('onboarding_seen_$sessionId', true);
    if (completed) await prefs.remove(key);
  }
}

String destinationForProfile(Map<String, dynamic> profile,
    {required bool dismissed, required bool hasDraft}) {
  if (dismissed) return '/';
  if (hasDraft) return '/onboarding';
  final incomplete = (profile['name']?.toString().trim() ?? '').isEmpty ||
      (profile['state']?.toString().trim() ?? '').isEmpty ||
      (profile['crops'] is! List || (profile['crops'] as List).isEmpty) ||
      profile['land_size_acres'] == null;
  return incomplete ? '/onboarding' : '/';
}
