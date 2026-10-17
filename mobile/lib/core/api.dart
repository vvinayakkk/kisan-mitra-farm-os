import 'dart:async';
import 'dart:convert';

import 'package:easy_localization/easy_localization.dart';
import 'package:http/http.dart' as http;

import 'config.dart';
import 'offline.dart';
import 'read_cache.dart';

/// Server-issued assistant session capability. The farmer identity behind it is
/// resolved by the backend; the app never sends a farmer id.
class SessionCapability {
  const SessionCapability({required this.id, required this.token});

  final String id;
  final String token;

  static final _id = RegExp(r'^[a-f0-9]{32}$');

  static SessionCapability? tryParse(Object? value) {
    if (value is! Map) return null;
    final id = value['id'] ?? value['session_id'];
    final token = value['token'];
    if (id is! String ||
        !_id.hasMatch(id) ||
        token is! String ||
        token.isEmpty) {
      return null;
    }
    return SessionCapability(id: id, token: token);
  }

  Map<String, String> get headers => {
        'Authorization': 'Bearer $token',
        'X-Assistant-Session': id,
      };

  Map<String, String> toJson() => {'id': id, 'token': token};
}

class ApiException implements Exception {
  ApiException(this.status, this.message);

  /// 0 means the request never reached the server.
  final int status;
  final String message;

  bool get unauthorized => status == 401;
  bool get conflict => status == 409;
  bool get offline => status == 0;

  @override
  String toString() => message;
}

String _detail(String body, int status) {
  // Unexpected server faults get plain words; the server's specific reasons
  // (validation, "not configured", conflicts) are kept.
  if (status >= 500 && status != 503) return 'fos.label.err_server'.tr();
  try {
    final data = jsonDecode(body);
    final detail = data is Map ? data['detail'] : null;
    if (detail is String && detail.isNotEmpty) return detail;
    // Pydantic field errors are developer text; farmers get a plain hint.
    if (detail is List && detail.isNotEmpty) {
      return 'fos.label.err_check_input'.tr();
    }
  } catch (_) {}
  return (status == 503 || status == 429
          ? 'fos.label.err_busy'
          : 'fos.label.err_server')
      .tr();
}

/// Thin JSON client. One instance per session capability so a request started
/// for one farmer can never complete into another farmer's state.
class ApiClient {
  ApiClient(
      {this.session,
      http.Client? client,
      String? baseUrl,
      this.offline,
      this.cacheReads = false, this.isOffline})
      : _client = client ?? http.Client(),
        base = (baseUrl ?? AppConfig.apiBaseUrl).replaceAll(RegExp(r'/$'), '');

  final SessionCapability? session;
  final http.Client _client;

  /// Saved copies for a few read screens; used only when the network fails.
  final OfflineStore? offline;
  final String base;
  final bool cacheReads;
  final bool Function()? isOffline;
  final _reads = ReadCache(ttl: const Duration(seconds: 45));
  void invalidateReads() => _reads.invalidate();

  /// Called when the server rejects the capability; the app signs out.
  void Function()? onUnauthorized;

  Uri uri(String path, [Map<String, Object?>? query]) {
    final q = <String, String>{};
    query?.forEach((k, v) {
      if (v != null && '$v'.isNotEmpty) q[k] = '$v';
    });
    return Uri.parse('$base$path')
        .replace(queryParameters: q.isEmpty ? null : q);
  }

  Map<String, String> headers({bool json = true}) => {
        if (json) 'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...?session?.headers,
      };

  Future<dynamic> get(String path,
      {Map<String, Object?>? query,
      Duration timeout = const Duration(seconds: 25),
      bool fresh = false, bool allowSaved = true}) {
    final key = uri(path, query).toString();
    Future<dynamic> fetch() => _withSavedCopy(
        allowSaved && OfflineStore.cacheable(path) ? key : null,
        () => _send(
            () => _client.get(uri(path, query), headers: headers()), timeout));
    // Session snapshots/events and jobs are authoritative on every read.
    final cached = OfflineStore.cacheable(path) &&
        !path.startsWith('/api/assistant/sessions/');
    return cacheReads && cached && !fresh && allowSaved ? _reads.read(key, fetch) : fetch();
  }

  /// Live result is saved; with no network the last saved copy is returned
  /// (and [OfflineStore.servedSavedAt] tells the UI how old it is).
  Future<dynamic> _withSavedCopy(
      String? key, Future<dynamic> Function() load) async {
    final store = offline;
    if (store == null || key == null) return load();
    if (isOffline?.call() == true) {
      final saved = await store.load(key);
      if (saved != null) return saved.data;
      throw ApiException(0, 'fos.label.err_offline'.tr());
    }
    try {
      final data = await load();
      unawaited(store.save(key, data));
      return data;
    } on ApiException catch (e) {
      if (!e.offline) rethrow;
      final saved = await store.load(key);
      if (saved == null) rethrow;
      return saved.data;
    }
  }

  Future<dynamic> post(String path,
          {Object? body,
          Map<String, String>? extraHeaders,
          Duration timeout = const Duration(seconds: 30),
          bool saveCopy = false}) =>
      saveCopy
          ? _withSavedCopy(
              '$path ${jsonEncode(body)}',
              () => post(path,
                  body: body, extraHeaders: extraHeaders, timeout: timeout))
          : _send(
              () => _client.post(uri(path),
                  headers: {...headers(), ...?extraHeaders},
                  body: body == null ? null : jsonEncode(body)),
              timeout);

  Future<dynamic> put(String path, {Object? body}) => _send(
      () => _client.put(uri(path),
          headers: headers(), body: jsonEncode(body ?? {})),
      const Duration(seconds: 30));

  Future<dynamic> patch(String path,
          {Object? body, Map<String, String>? extraHeaders}) =>
      _send(
          () => _client.patch(uri(path),
              headers: {...headers(), ...?extraHeaders},
              body: jsonEncode(body ?? {})),
          const Duration(seconds: 30));

  Future<dynamic> delete(String path,
          {Map<String, String>? extraHeaders}) =>
      _send(
          () => _client
              .delete(uri(path), headers: {...headers(), ...?extraHeaders}),
          const Duration(seconds: 30));

  /// Multipart upload (audio, images). Returns decoded JSON.
  Future<dynamic> multipart(String path, http.MultipartFile file,
      {Map<String, String> fields = const {},
      Duration timeout = const Duration(seconds: 60)}) {
    return _send(() async {
      final request = http.MultipartRequest('POST', uri(path))
        ..headers.addAll(headers(json: false))
        ..fields.addAll(fields)
        ..files.add(file);
      return http.Response.fromStream(await _client.send(request));
    }, timeout);
  }

  /// Raw bytes (file downloads).
  Future<http.Response> bytes(String path) async {
    final response = await _guard(
        () => _client.get(uri(path), headers: headers(json: false)),
        const Duration(seconds: 60));
    _check(response);
    return response;
  }

  /// Streaming POST used by assistant runs. Caller owns cancellation via
  /// [http.Client.close] on [client].
  Future<http.StreamedResponse> stream(
      String path, Object body, http.Client client) async {
    final request = http.Request('POST', uri(path))
      ..headers.addAll({...headers(), 'Accept': 'application/x-ndjson'})
      ..body = jsonEncode(body);
    final response =
        await client.send(request).timeout(const Duration(seconds: 30));
    if (response.statusCode >= 400) {
      final text = await response.stream.bytesToString();
      if (response.statusCode == 401) onUnauthorized?.call();
      throw ApiException(
          response.statusCode, _detail(text, response.statusCode));
    }
    return response;
  }

  Future<http.Response> _guard(
      Future<http.Response> Function() call, Duration timeout) async {
    try {
      return await call().timeout(timeout);
    } on TimeoutException {
      throw ApiException(0, 'fos.label.err_timeout'.tr());
    } on http.ClientException {
      throw ApiException(0, 'fos.label.err_offline'.tr());
    }
  }

  void _check(http.Response response) {
    if (response.statusCode < 400) return;
    if (response.statusCode == 401) onUnauthorized?.call();
    throw ApiException(
        response.statusCode, _detail(response.body, response.statusCode));
  }

  Future<dynamic> _send(
      Future<http.Response> Function() call, Duration timeout) async {
    final response = await _guard(call, timeout);
    _check(response);
    if (response.request?.method != null && response.request!.method != 'GET' && !RegExp(r'^/api/assistant/sessions/[^/]+/inspect/(market_prices|market_trend|scheme_search)$').hasMatch(response.request!.url.path) && !{'/api/speech/synthesize', '/api/speech/transcribe', '/api/companion/prepare'}.contains(response.request!.url.path)) {
      invalidateReads();
    }
    if (response.body.isEmpty) return null;
    return jsonDecode(utf8.decode(response.bodyBytes));
  }

  void close() => _client.close();
}
