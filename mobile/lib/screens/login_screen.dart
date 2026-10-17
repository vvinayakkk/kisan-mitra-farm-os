import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/session.dart';
import '../ui/kit.dart';
import '../utils/constants.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final phone = TextEditingController(text: '+91');
  final code = TextEditingController();

  @override
  void dispose() {
    phone.dispose();
    code.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
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
                  else if (auth.mode == BackendMode.demo)
                    SizedBox(width: 220, height: 48, child: FilledButton(
                      onPressed: () { HapticFeedback.mediumImpact(); controller.signInDemo(); },
                      child: Text('splash.get_started'.tr()),
                    ))
                  else if (auth.mode == BackendMode.live)
                    Column(children: [
                      TextField(
                        controller: phone,
                        enabled: !auth.codeSent,
                        keyboardType: TextInputType.phone,
                        autofillHints: const [AutofillHints.telephoneNumber],
                        decoration: InputDecoration(labelText: 'fos.auth.mobile_number'.tr(), hintText: '+91 98765 43210', border: const OutlineInputBorder()),
                      ),
                      if (auth.codeSent) ...[
                        const SizedBox(height: 12),
                        TextField(
                          controller: code,
                          keyboardType: TextInputType.number,
                          autofillHints: const [AutofillHints.oneTimeCode],
                          maxLength: 6,
                          decoration: InputDecoration(labelText: 'fos.auth.six_digit_code'.tr(), border: const OutlineInputBorder(), counterText: ''),
                          onSubmitted: (_) => controller.confirmPhoneCode(code.text.trim()),
                        ),
                      ],
                      const SizedBox(height: 16),
                      SizedBox(width: double.infinity, height: 48, child: FilledButton(
                        onPressed: () {
                          HapticFeedback.mediumImpact();
                          auth.codeSent ? controller.confirmPhoneCode(code.text.trim()) : controller.sendPhoneCode(phone.text.trim());
                        },
                        child: Text(auth.codeSent ? 'fos.auth.verify_continue'.tr() : 'fos.auth.send_code'.tr()),
                      )),
                      if (auth.codeSent) TextButton(
                        onPressed: () => controller.sendPhoneCode(phone.text.trim()),
                        child: Text('fos.auth.resend_code'.tr()),
                      ),
                    ])
                  else
                    ErrorView(auth.error ?? 'fos.assistant.server_unreachable'.tr(), onRetry: controller.refreshMode),
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
