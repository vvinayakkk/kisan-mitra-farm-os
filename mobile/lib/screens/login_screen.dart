import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

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
                  Text('welcome'.tr(),
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 26, fontWeight: FontWeight.w700, color: ink)),
                  const SizedBox(height: 6),
                  Text('splash.subtitle'.tr(), textAlign: TextAlign.center, style: TextStyle(color: mutedColor(context))),
                  const SizedBox(height: 28),
                  if (auth.status == AuthStatus.loading || auth.busy)
                    const Padding(padding: EdgeInsets.all(12), child: CircularProgressIndicator())
                  else if (auth.mode == BackendMode.demo || auth.mode == BackendMode.live)
                    SizedBox(
                      width: 220,
                      height: 48,
                      child: FilledButton(
                        onPressed: () {
                          HapticFeedback.mediumImpact();
                          auth.mode == BackendMode.demo ? controller.signInDemo() : controller.signInLive();
                        },
                        child: Text('splash.get_started'.tr()),
                      ),
                    )
                  else
                    ErrorView(auth.error ?? 'Could not reach the server.', onRetry: controller.refreshMode),
                  if (auth.error != null && (auth.mode == BackendMode.demo || auth.mode == BackendMode.live))
                    ErrorView(auth.error!),
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
