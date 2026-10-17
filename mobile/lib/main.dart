import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'router.dart';
import 'ui/offline_banner.dart';
import 'services/theme_service.dart';
import 'utils/constants.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await EasyLocalization.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(statusBarColor: Colors.transparent));
  runApp(
    EasyLocalization(
      supportedLocales: const [
        Locale('en'), Locale('hi'), Locale('mr'), Locale('te'), Locale('ta'),
        Locale('gu'), Locale('bn'), Locale('kn'), Locale('ml'), Locale('pa'),
      ],
      path: 'assets/translations',
      fallbackLocale: const Locale('en'),
      child: const ProviderScope(child: KisanMitraApp()),
    ),
  );
}

class KisanMitraApp extends ConsumerWidget {
  const KisanMitraApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) => MaterialApp.router(
        title: 'Kisan Mitra',
        debugShowCheckedModeBanner: false,
        theme: buildAppTheme(dark: false),
        darkTheme: buildAppTheme(dark: true),
        themeMode: ref.watch(themeProvider),
        routerConfig: ref.watch(routerProvider),
        localizationsDelegates: context.localizationDelegates,
        supportedLocales: context.supportedLocales,
        locale: context.locale,
        builder: (context, child) => OfflineFrame(child: child!),
      );
}
