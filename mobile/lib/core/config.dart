/// Build-time configuration. Every value here is bundled into the app, so none
/// of them may be a secret.
abstract final class AppConfig {
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8001',
  );

  static const stationId = String.fromEnvironment(
    'STATION_ID',
    defaultValue: 'WS01',
  );
}
