import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/config.dart';
import '../core/session.dart';
import '../ui/kit.dart';
import '../utils/constants.dart';

/// Sign-in follows the server's lane: the demo lane issues an explicit demo
/// session; the live lane requires a verified account (OIDC). The app never
/// picks a farmer itself.
class LoginScreen extends ConsumerWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);
    final controller = ref.read(authProvider.notifier);
    final ink = inkColor(context);
    return Scaffold(
      body: FarmBackground(
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 380),
                child: Column(children: [
                  Image.asset(context.isDark ? 'assets/logo_light.png' : 'assets/logo.png', width: 200, height: 200),
                  Text('Kisan Mitra', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: ink)),
                  const SizedBox(height: 6),
                  Text('Your farm records, plans and assistant in one place.',
                      textAlign: TextAlign.center, style: TextStyle(color: mutedColor(context))),
                  const SizedBox(height: 28),
                  if (auth.status == AuthStatus.loading || auth.busy)
                    const LoadingView('Connecting…')
                  else ...switch (auth.mode) {
                    BackendMode.demo => [
                        FilledButton.icon(
                          style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                          onPressed: controller.signInDemo,
                          icon: const Icon(Icons.agriculture),
                          label: const Text('Open the demo farm'),
                        ),
                        const SizedBox(height: 8),
                        Text('This server runs with sample data. No SMS is sent and no real account is created.',
                            textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: mutedColor(context))),
                      ],
                    BackendMode.live => [
                        FilledButton.icon(
                          style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                          onPressed: AppConfig.oidcConfigured ? controller.signInLive : null,
                          icon: const Icon(Icons.verified_user_outlined),
                          label: const Text('Sign in'),
                        ),
                        if (!AppConfig.oidcConfigured)
                          Padding(
                            padding: const EdgeInsets.only(top: 8),
                            child: Text('This build has no sign-in provider configured, so it cannot open a live account.',
                                textAlign: TextAlign.center, style: TextStyle(fontSize: 12, color: mutedColor(context))),
                          ),
                      ],
                    _ => [
                        ErrorView(
                          auth.mode == BackendMode.unsupported
                              ? 'This server is not running the Farm OS data platform.'
                              : 'Could not reach the Kisan Mitra server.',
                          onRetry: controller.refreshMode,
                        ),
                      ],
                  },
                  if (auth.error != null) ErrorView(auth.error!),
                  const SizedBox(height: 18),
                  Text(AppConfig.apiBaseUrl, style: TextStyle(fontSize: 11, color: mutedColor(context))),
                  const SizedBox(height: 4),
                  const Icon(Icons.lock_outline, size: 14, color: AppColors.textMuted),
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
