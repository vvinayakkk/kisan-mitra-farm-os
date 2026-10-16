import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'assistant/chat_screen.dart';
import 'core/session.dart';
import 'features/calendar_screen.dart';
import 'features/crop_doctor_screen.dart';
import 'features/exchange/exchange_screen.dart';
import 'features/exchange/thread_screen.dart';
import 'features/home_shell.dart';
import 'features/markets_screen.dart';
import 'features/notebook/notebook_screen.dart';
import 'features/profile_screen.dart';
import 'features/saathi.dart';
import 'features/schemes_screen.dart';
import 'features/station_screen.dart';
import 'features/weather_screen.dart';
import 'screens/language_select_screen.dart';
import 'screens/login_screen.dart';
import 'screens/splash_screen.dart';

const _public = {'/splash', '/language_select', '/login'};

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier(0);
  ref.listen(authProvider.select((s) => (s.status, s.session?.id)), (_, __) => refresh.value++);
  ref.onDispose(refresh.dispose);

  return GoRouter(
    initialLocation: '/splash',
    refreshListenable: refresh,
    redirect: (context, state) {
      final auth = ref.read(authProvider);
      final here = state.matchedLocation;
      if (auth.status == AuthStatus.loading) return here == '/splash' ? null : '/splash';
      if (!auth.isAuthenticated) {
        if (_public.contains(here)) return null;
        // A session that ended mid-use goes straight to sign-in.
        return '/login';
      }
      if (here == '/login' || here == '/language_select') return '/';
      return null;
    },
    routes: [
      GoRoute(path: '/splash', pageBuilder: (_, s) => _fade(s, const SplashScreen())),
      GoRoute(path: '/language_select', pageBuilder: (_, s) => _fade(s, const LanguageSelectScreen())),
      GoRoute(path: '/login', pageBuilder: (_, s) => _fade(s, const LoginScreen())),
      GoRoute(path: '/', pageBuilder: (_, s) => _fade(s, const HomeShell())),
      GoRoute(path: '/chat', builder: (_, __) => const ChatScreen()),
      GoRoute(path: '/calendar', builder: (_, __) => const CalendarScreen()),
      GoRoute(path: '/station', builder: (_, __) => const StationScreen()),
      GoRoute(path: '/weather', builder: (_, __) => const WeatherScreen()),
      GoRoute(path: '/crops', builder: (_, __) => const CropDoctorScreen()),
      GoRoute(path: '/markets', builder: (_, __) => const MarketsScreen()),
      GoRoute(path: '/schemes', builder: (_, __) => const SchemesScreen()),
      GoRoute(path: '/notebook', builder: (_, s) => NotebookScreen(initialTab: s.uri.queryParameters['tab'])),
      GoRoute(path: '/exchange', builder: (_, __) => const ExchangeScreen()),
      GoRoute(
        path: '/exchange/thread/:id',
        redirect: (_, s) => RegExp(r'^[a-f0-9-]{36}$').hasMatch(s.pathParameters['id'] ?? '') ? null : '/exchange',
        builder: (_, s) => ThreadScreen(threadId: s.pathParameters['id']!),
      ),
      GoRoute(path: '/saathi', builder: (_, __) => const SaathiScreen()),
      GoRoute(path: '/profile', builder: (_, __) => const ProfileScreen()),
    ],
  );
});

CustomTransitionPage<void> _fade(GoRouterState state, Widget child) => CustomTransitionPage<void>(
      key: state.pageKey,
      child: child,
      transitionsBuilder: (_, anim, __, c) => FadeTransition(opacity: anim, child: c),
      transitionDuration: const Duration(milliseconds: 240),
    );
