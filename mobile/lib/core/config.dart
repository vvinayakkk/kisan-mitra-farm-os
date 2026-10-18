/// Build-time configuration. Every value here is bundled into the app, so none
/// of them may be a secret.
abstract final class AppConfig {
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://kisan-mitra-api-344920654513.asia-south1.run.app',
  );

  static const stationId = String.fromEnvironment(
    'STATION_ID',
    defaultValue: 'WS01',
  );
}
