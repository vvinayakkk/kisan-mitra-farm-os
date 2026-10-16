/// Build-time configuration. Every value here is bundled into the app, so none
/// of them may be a secret.
abstract final class AppConfig {
  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8001',
  );

  /// OIDC settings for live mode. The backend verifies the resulting token
  /// against its own issuer/audience/JWKS; the app never decides identity.
  static const oidcIssuer = String.fromEnvironment('OIDC_ISSUER');
  static const oidcClientId = String.fromEnvironment('OIDC_CLIENT_ID');
  static const oidcRedirectUri = String.fromEnvironment(
    'OIDC_REDIRECT_URI',
    defaultValue: 'com.initio.kisanmitra:/oauthredirect',
  );
  static const oidcAudience = String.fromEnvironment('OIDC_AUDIENCE');

  static bool get oidcConfigured =>
      oidcIssuer.isNotEmpty && oidcClientId.isNotEmpty;

  static const stationId = String.fromEnvironment(
    'STATION_ID',
    defaultValue: 'WS01',
  );
}
