import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_riverpod/legacy.dart';
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Last successful copies of a few read-only screens (mandi, weather, tasks,
/// notebook, station), kept per session on the phone so a farmer with no
/// signal still sees what they last loaded — always labelled with its time.
/// Nothing is written while offline and no data is invented.
class OfflineStore {
  OfflineStore(this.sessionId,
      {Future<Directory> Function()? root, this.maxEntries = 80})
      : _root = root ?? getApplicationSupportDirectory;

  final String sessionId;
  final int maxEntries;
  final Future<Directory> Function() _root;

  /// Time of the saved copy currently on screen; null while data is live.
  final servedSavedAt = ValueNotifier<DateTime?>(null);

  static const _paths = [
    '/api/assistant/sessions/',
    '/api/assistant/catalog',
    '/api/assistant/station/',
    '/api/weather/dashboard',
    '/api/farm-workspace/',
    '/api/profile',
    '/api/farms',
    '/api/plots',
    '/api/crop-cycles',
    '/api/onboarding/options',
    '/api/mandi/catalogue',
    '/api/companion',
    '/api/exchange/listings',
    '/api/sensors/stations',
  ];

  static bool cacheable(String path) =>
      _paths.any(path.startsWith) && !path.contains('/events');

  Future<Directory> _dir() async {
    final dir = Directory('${(await _root()).path}/offline/$sessionId');
    await dir.create(recursive: true);
    return dir;
  }

  /// FNV-1a: stable across runs (String.hashCode is not).
  static String fileName(String key) {
    var h = 0xcbf29ce484222325;
    for (final c in utf8.encode(key)) {
      h ^= c;
      h = (h * 0x100000001b3) & 0xFFFFFFFFFFFFFFFF;
    }
    return '${h.toRadixString(16)}.json';
  }

  Future<void> save(String key, Object? data) async {
    try {
      final dir = await _dir();
      await File('${dir.path}/${fileName(key)}').writeAsString(jsonEncode(
          {'saved_at': DateTime.now().toIso8601String(), 'data': data}));
      final files = dir.listSync().whereType<File>().toList()
        ..sort((a, b) => a.lastModifiedSync().compareTo(b.lastModifiedSync()));
      for (final f
          in files.take((files.length - maxEntries).clamp(0, files.length))) {
        f.deleteSync();
      }
      servedSavedAt.value = null;
    } catch (_) {
      // A full or unavailable disk only loses the offline copy.
    }
  }

  Future<({Object? data, DateTime savedAt})?> load(String key) async {
    try {
      final file = File('${(await _dir()).path}/${fileName(key)}');
      if (!file.existsSync()) return null;
      final j = jsonDecode(await file.readAsString()) as Map<String, dynamic>;
      final savedAt = DateTime.parse(j['saved_at'] as String);
      servedSavedAt.value = savedAt;
      return (data: j['data'], savedAt: savedAt);
    } catch (_) {
      return null;
    }
  }

  /// Erases every saved copy on this phone (sign-out or ended session).
  static Future<void> clearAll({Future<Directory> Function()? root}) async {
    try {
      final dir = Directory(
          '${(await (root ?? getApplicationSupportDirectory)()).path}/offline');
      if (dir.existsSync()) await dir.delete(recursive: true);
    } catch (_) {}
    try {
      final prefs = await SharedPreferences.getInstance();
      for (final key in prefs.getKeys().where(
          (k) => k.startsWith('onboarding_draft_') || k.startsWith('onboarding_seen_') || k.startsWith('outbox_') || k.startsWith('chat_draft_'))) {
        await prefs.remove(key);
      }
    } catch (_) {}
  }
}

bool isOffline(List<ConnectivityResult> results) =>
    results.isEmpty || results.every((r) => r == ConnectivityResult.none);

/// True while the phone has no network at all.
final offlineProvider = StreamProvider<bool>((ref) async* {
  final connectivity = Connectivity();
  yield isOffline(await connectivity.checkConnectivity());
  yield* connectivity.onConnectivityChanged.map(isOffline);
});

/// Successful reconnect refreshes visible read screens without remounting them.
final syncRevisionProvider = StateProvider<int>((ref) => 0);
