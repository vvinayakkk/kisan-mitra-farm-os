# Kisan Mitra mobile

The Flutter client for Farm OS: agentic chat, voice, calendar, Saathi, station, weather, crop doctor, markets, schemes, notebook, exchange and profile. It uses the canonical backend and the same farmer records as the web workspace. The architecture, identity lifecycle, configuration, permissions and release steps are in the [mobile guide](../docs/mobile/README.md); feature coverage is in the [parity matrix](../docs/mobile/parity.md).

```bash
flutter pub get
flutter test
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8001
```

Release builds sign only with a private keystore configured in the ignored `android/key.properties`. Without one, the release APK stays unsigned. Build outputs are ignored by Git.
