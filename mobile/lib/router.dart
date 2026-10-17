import 'tour/app_tour.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'assistant/chat_screen.dart';
import 'core/session.dart';
import 'core/launch.dart';
import 'features/calendar_screen.dart';
import 'features/crop_doctor_screen.dart';
import 'features/exchange/exchange_screen.dart';
import 'features/exchange/thread_screen.dart';
import 'features/markets_screen.dart';
import 'features/notebook/notebook_screen.dart';
import 'features/profile_screen.dart';
import 'features/saathi.dart';
import 'features/schemes_screen.dart';
import 'features/station_screen.dart';
import 'features/weather_screen.dart';
import 'screens/choice_screen.dart';
import 'screens/onboarding_screen.dart';
import 'screens/language_select_screen.dart';
import 'screens/login_screen.dart';
import 'screens/splash_screen.dart';

const _public = {'/splash', '/language_select', '/login'};

final routerProvider = Provider<GoRouter>((ref) {
  final refresh = ValueNotifier(0);
  ref.listen(authProvider.select((s) => (s.status, s.session?.id)),
      (_, __) => refresh.value++);
  ref.listen(launchDestinationProvider, (_, __) => refresh.value++);
  ref.listen(launchAnimationProvider, (_, __) => refresh.value++);
  ref.onDispose(refresh.dispose);

  return GoRouter(
    initialLocation: '/splash',
    refreshListenable: refresh,
    redirect: (context, state) {
      final auth = ref.read(authProvider);
      final here = state.matchedLocation;
      if (auth.status == AuthStatus.loading) {
        return here == '/splash' ? null : '/splash';
      }
      final destination = ref.read(launchDestinationProvider);
      if (here == '/splash') {
        if (ref.read(launchAnimationProvider).isLoading || destination.isLoading) return null;
        return destination.asData?.value == '/splash' ? null : (destination.asData?.value ?? '/login');
      }
      if (!auth.isAuthenticated) {
        if (_public.contains(here)) return null;
        // A session that ended mid-use goes straight to sign-in.
        return '/login';
      }
      if (here == '/splash' || here == '/login' || here == '/language_select') {
        return destination.asData?.value ?? '/splash';
      }
      return null;
    },
    routes: [
      GoRoute(
          path: '/splash',
          pageBuilder: (_, s) => _fade(s, const SplashScreen())),
      GoRoute(
          path: '/language_select',
          pageBuilder: (_, s) => _fade(s, const LanguageSelectScreen())),
      GoRoute(
          path: '/login', pageBuilder: (_, s) => _fade(s, const LoginScreen())),
      GoRoute(path: '/', pageBuilder: (_, s) => _fade(s, const AppTour(scope: 'home', child: ChoiceScreen()))),
      GoRoute(
          path: '/onboarding',
          pageBuilder: (_, s) => _fade(s, const AppTour(scope: 'onboarding', child: OnboardingScreen()))),
      GoRoute(path: '/choice', redirect: (_, __) => '/'),
      GoRoute(path: '/chat', builder: (_, __) => const AppTour(scope: 'chat', child: ChatScreen())),
      GoRoute(path: '/calendar', builder: (_, __) => const AppTour(scope: 'calendar', child: CalendarScreen())),
      GoRoute(path: '/station', builder: (_, __) => const AppTour(scope: 'station', child: StationScreen())),
      GoRoute(path: '/weather', builder: (_, __) => const AppTour(scope: 'weather', child: WeatherScreen())),
      GoRoute(path: '/crops', builder: (_, __) => const AppTour(scope: 'crops', child: CropDoctorScreen())),
      GoRoute(path: '/markets', builder: (_, __) => const AppTour(scope: 'markets', child: MarketsScreen())),
      GoRoute(path: '/schemes', builder: (_, __) => const AppTour(scope: 'schemes', child: SchemesScreen())),
      GoRoute(
          path: '/notebook',
          builder: (_, s) =>
              AppTour(scope: 'notebook', child: NotebookScreen(initialTab: s.uri.queryParameters['tab']))),
      GoRoute(path: '/exchange', builder: (_, __) => const AppTour(scope: 'exchange', child: ExchangeScreen())),
      GoRoute(
        path: '/exchange/thread/:id',
        redirect: (_, s) =>
            RegExp(r'^[a-f0-9-]{36}$').hasMatch(s.pathParameters['id'] ?? '')
                ? null
                : '/exchange',
        builder: (_, s) => ThreadScreen(threadId: s.pathParameters['id']!),
      ),
      GoRoute(path: '/saathi', builder: (_, __) => const AppTour(scope: 'saathi', child: SaathiScreen())),
      GoRoute(path: '/profile', builder: (_, __) => const AppTour(scope: 'profile', child: ProfileScreen())),
    ],
  );
});

CustomTransitionPage<void> _fade(GoRouterState state, Widget child) =>
    CustomTransitionPage<void>(
      key: state.pageKey,
      child: child,
      transitionsBuilder: (context, anim, __, c) => MediaQuery.disableAnimationsOf(context) ? c : FadeTransition(
          opacity: anim,
          child: SlideTransition(
              position: Tween(begin: const Offset(.025, 0), end: Offset.zero)
                  .animate(CurvedAnimation(
                      parent: anim, curve: Curves.easeOutCubic)),
              child: c)),
      transitionDuration: const Duration(milliseconds: 240),
    );
