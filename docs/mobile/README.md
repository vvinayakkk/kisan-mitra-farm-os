# Flutter client

The Flutter project in `mobile/` is the phone version of Farm OS. It talks to the same canonical backend and farmer records as the web workspace, through the same assistant session. It is a native client, not a WebView. Feature coverage against the web is tracked in the [parity matrix](parity.md).

## Structure

| Path | Responsibility |
| --- | --- |
| `lib/core/` | `ApiClient` (session headers, typed errors, timeouts, NDJSON streaming), `AuthController` and `SessionVault` (identity lifecycle), bounded `ReadCache`, language preference, idempotency keys |
| `lib/assistant/` | Typed assistant models, the pure event reducer `run_events.dart`, `AssistantController` (run, stop, retry, approve/decline/answer, history, restart recovery, task edits), chat screen, page helper sheet, widgets for messages, activity, pending cards, results and the composer |
| `lib/voice/` | Speech capabilities, microphone consent, WAV recording, transcription, synthesis/playback, the dictation button and the turn-based live voice sheet |
| `lib/features/` | Calendar, Saathi, Station, Weather, Crop doctor, Markets, Schemes, Notebook (Today, Fields, Money, Follow-ups, Plans, Memory, Files, shared work), Exchange and Profile |
| `lib/ui/` | Shared look (gradient background, cards, the original outlined chips), loading/empty/error views, provenance badge, form sheet |
| `test/` | Contract and failure-path tests: stream ends early, 401, stop, restart replay, stale undo, cache bounds, language/speech, auth lanes |

Navigation keeps the original app: splash → language → sign in → choice screen (voice, text chat, quick services). Chat's suggestion chips open every Farm OS tool (calendar, crop doctor, mandi, weather, station, schemes, notebook, exchange, Saathi, profile, skills, language). Every tool screen has an "Ask Mitra" helper. The theme follows the original design: Poppins, light green gradient, frosted glass cards, filled buttons, centered titles and haptic feedback.

## Identity and session lifecycle

1. On launch the app reads `GET /` and shows the sign-in that matches `data_mode`.
2. **Demo lane (`v3_demo`)**: "Open the demo farm" requests the server's explicit demo challenge (`/api/auth/send-otp`, then `/verify-otp`). No SMS is sent. The server returns an assistant session capability.
3. **Live lane (`v3_live`)**: Firebase Phone Authentication verifies an Indian mobile number. The Firebase ID token is sent to `POST /api/assistant/sessions`; the server verifies its project, signature and phone provider before binding the farm session to that account. The Android Firebase app is registered under `com.initio.kisanmitra`, with release-certificate fingerprints configured.
4. Only the session capability `{id, token}` is stored, in the platform Keystore. Every private request sends `Authorization: Bearer <token>` and `X-Assistant-Session: <id>`. The app never sends a farmer ID.
5. An expired capability can be renewed through the persisted Firebase identity; a rejected renewal returns to sign-in. Sign-out revokes the session on the server, preserving history, then wipes local secrets and the read cache.

## Run locally

Requirements: Flutter 3.47 (Dart ≥3.4), Android SDK with platform 36, Java 17 or 21.

```bash
cd mobile
flutter pub get
flutter analyze
flutter test
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8001
```

`10.0.2.2` is the Android emulator's address for the host's loopback. A physical phone needs an origin it can reach. Debug builds allow cleartext HTTP for local development. Release builds allow HTTPS only (`usesCleartextTraffic=false`).

| `--dart-define` | Purpose | Default |
| --- | --- | --- |
| `API_BASE_URL` | Canonical API origin | `http://10.0.2.2:8001` |
| `STATION_ID` | Station to show | `WS01` |

These values are compiled into the app. None of them may be a secret.

## Permissions

| Permission | Use | Requested |
| --- | --- | --- |
| `INTERNET`, `ACCESS_NETWORK_STATE` | API calls | install time |
| `RECORD_AUDIO` | Dictation and live voice, only while recording | at first use, after an in-app explanation; a permanent denial links to Settings |
| Camera | Crop and document photos through the system camera app (intent) | no app permission declared; the camera app handles capture |
| Files / photos | System pickers only (no broad media access; video/audio media permissions removed) | none |

iOS `Info.plist` has microphone, camera and photo-library usage strings. iOS was not built here because full Xcode is not installed. `NSAllowsArbitraryLoads` remains for local development and must be removed for a production iOS build.

## Release

Release signing is read from an ignored `mobile/android/key.properties` or the same values in environment variables. A release build **without** these values is left unsigned; it never falls back to the debug key. Keep the release keystore and passwords private and backed up outside Git. The registered Firebase SHA-1 and SHA-256 must match this keystore for phone verification.

```properties
# mobile/android/key.properties  (ignored by Git; never commit)
storeFile=../kisan-mitra-release.keystore
storePassword=…
keyAlias=kisan-mitra-release
keyPassword=…
```

Environment alternative: `KISAN_MITRA_KEYSTORE`, `KISAN_MITRA_KEYSTORE_PASSWORD`, `KISAN_MITRA_KEY_ALIAS`, `KISAN_MITRA_KEY_PASSWORD`.

The signing files are ignored by Git. Losing the key prevents updates to the same installed app identity.

Build, verify and publish a draft release on the private repository:

```bash
cd mobile && flutter build apk --release --dart-define=API_BASE_URL=https://your-api.example
```

```bash
$ANDROID_HOME/build-tools/35.0.0/apksigner verify --print-certs mobile/build/app/outputs/flutter-apk/app-release.apk
```

```bash
gh release create mobile-v1.0.0 mobile/build/app/outputs/flutter-apk/app-release.apk --repo vvinayakkk/kisan-mitra-farm-os --draft --title "Kisan Mitra mobile 1.0.0" --notes "Signed Android build of the Farm OS mobile client."
```

Build outputs stay in `mobile/build/` (ignored). No APK is tracked in Git.

## Verification and limits

`flutter analyze`, `flutter test`, the backend suite (`data_platform/v3/test_backend.py`) and a walkthrough on Android emulators (Pixel 4 size and Pixel 7 Pro size with 130% font and dark theme) against the local canonical backend cover the flows in the parity matrix. The walkthrough was not run on a physical device. These items still need one:

- Spoken input end to end: the emulator ran without audio input. Recording, consent, transcription error handling and playback were exercised. Provider transcription was verified separately with a Hindi round trip through `/api/speech/synthesize` and `/api/speech/transcribe`.
- Live Firebase Phone sign-in: the controller's code and session handshake are tested, but a physical-phone SMS or Play Integrity run remains to be checked.
- Play/store distribution and iOS builds.

The interface ships in English, Hindi, Marathi, Telugu, Tamil, Gujarati, Bengali, Kannada, Malayalam and Punjabi (`assets/translations/`; a test checks every language has every key with matching placeholders). Odia, Assamese and Urdu fall back to English text, while the assistant still answers in the farmer's own language. With the 1.1.0 backend deployed, archived conversation history is scoped to the verified farmer and remains accessible across session renewal.

Weak networks: the last successful copy of the assistant session, mandi prices and trends, weather, notebook, station, profile and Saathi is kept per session on the phone (bounded, erased at sign-out). With no network those screens show the saved copy under a banner stating its time. Chat messages typed offline wait in an outbox and are sent in order when the network returns, stopping at any question or approval card. Writes (saving tasks, ledger entries, approvals, uploads) still need a connection.

## Version 1.1.0

See [release changes and deployment requirements](../releases/v1.1.0.md) for the updated launch, onboarding, voice, offline and interface behavior. New copy is not yet fully localized.
