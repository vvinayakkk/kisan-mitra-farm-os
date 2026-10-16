# Kisan Mitra mobile client

This is the Flutter source project for the companion mobile client. The web Farm OS and API live at the repository root. Mobile architecture, supported screens, configuration and build steps are in the [mobile guide](../docs/mobile/README.md).

Run `flutter pub get` from this directory, then provide an API origin with `--dart-define=API_BASE_URL=https://your-api.example`. Android emulator development defaults to `http://10.0.2.2:8001`; a physical device or iOS simulator needs an explicitly reachable origin. Android's release configuration currently uses the debug signing key, so its APK is suitable for local review only. Configure a private release keystore before distribution.

`flutter build apk --release` writes to `mobile/build/app/outputs/flutter-apk/app-release.apk`. Build outputs are ignored by Git; no APK is stored in this repository.
