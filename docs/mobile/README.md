# Flutter client

The Flutter project lives directly in `mobile/`. `mobile/lib/main.dart` initializes localization, Riverpod and the router. `lib/screens/` contains login, signup, overview, chat, voice, crop doctor, mandi, marketplace, profile, trends, reports and hardware screens. `lib/services/` owns HTTP, authentication, chat history, prefetch, theme and voice helpers. Translation assets currently include English and Hindi. The web Farm OS remains the primary reviewed experience; the mobile source is a separate client, not a packaged copy of the web app.

## Build and API origin

Use a compatible Flutter SDK (the `pubspec.yaml` Dart constraint is `>=3.4.0 <4.0.0`), Android SDK and Java 17. From `mobile/` run `flutter pub get`, `flutter analyze`, `flutter test`, then `flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8001` for an Android emulator. On a physical phone, use an API origin reachable from that device; for a hosted backend use HTTPS. The same value can be passed to `flutter build apk --release --dart-define=API_BASE_URL=https://your-api.example`.

The Android source currently sets `minSdk=24`, `targetSdk=35` and `compileSdk=36`. The release build uses the debug signing configuration in `android/app/build.gradle.kts`. Replace that with a private release keystore before distribution, then verify callback and API origins on a device. The APK is written to `mobile/build/app/outputs/flutter-apk/app-release.apk` and is ignored by Git. No APK is tracked in this repository.

## Ownership and compatibility

The mobile client still calls several classic-compatible API paths. Verify those paths against `/openapi.json` in the selected backend mode before field use. It should not be described as having every Farm OS workflow or offline capability simply because the web interface has them. Android requests internet, microphone, camera and location permissions; usage must follow runtime consent. Review the platform manifests and transport policy before a public release.
