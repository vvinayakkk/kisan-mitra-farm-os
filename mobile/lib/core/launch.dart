import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'session.dart';
import 'onboarding_progress.dart';

// Runs alongside auth restoration, never on ordinary screen navigation.
final launchAnimationProvider = FutureProvider<void>((ref) async {
  await Future<void>.delayed(const Duration(milliseconds: 650));
});

final launchDestinationProvider = FutureProvider<String>((ref) async {
  final auth = ref.watch(authProvider.select((s) => (s.status, s.session?.id)));
  if (auth.$1 == AuthStatus.loading) return '/splash';
  final prefs = await SharedPreferences.getInstance();
  if (auth.$1 != AuthStatus.signedIn || auth.$2 == null) {
    return prefs.getBool('has_signed_in') == true
        ? '/login'
        : '/language_select';
  }
  await prefs.setBool('has_signed_in', true);
  final progress = OnboardingProgress(prefs, auth.$2!);
  if (progress.dismissed) return '/';
  if (progress.read() != null) return '/onboarding';
  try {
    final result = await ref
        .read(apiProvider)
        .get('/api/profile', timeout: const Duration(seconds: 5));
    final profile = result is Map && result['profile'] is Map
        ? Map<String, dynamic>.from(result['profile'])
        : <String, dynamic>{};
    final destination = destinationForProfile(profile, dismissed: false, hasDraft: false);
    if (destination == '/') await progress.leave(completed: true);
    return destination;
  } catch (_) {
    // A slow/offline profile must not strand a returning farmer on launch.
    return '/';
  }
});
