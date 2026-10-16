/// Bounded in-memory read cache scoped to one session. It only smooths
/// navigation; the server stays authoritative. Entries expire after [ttl] and
/// the whole cache is cleared after any write or session change.
class ReadCache {
  ReadCache({this.maxEntries = 40, this.ttl = const Duration(minutes: 3)});

  final int maxEntries;
  final Duration ttl;
  final _entries = <String, (DateTime, Object?)>{};
  final _inflight = <String, Future<Object?>>{};
  int _generation = 0;

  Future<T> read<T>(String key, Future<T> Function() load, {DateTime Function()? now}) async {
    final clock = now ?? DateTime.now;
    final hit = _entries.remove(key);
    if (hit != null && clock().difference(hit.$1) < ttl) {
      _entries[key] = hit; // refresh LRU position
      return hit.$2 as T;
    }
    final pending = _inflight[key];
    if (pending != null) return await pending as T;
    final generation = _generation;
    final future = load();
    _inflight[key] = future;
    try {
      final value = await future;
      if (generation == _generation) {
        _entries[key] = (clock(), value);
        while (_entries.length > maxEntries) {
          _entries.remove(_entries.keys.first);
        }
      }
      return value;
    } finally {
      if (identical(_inflight[key], future)) _inflight.remove(key);
    }
  }

  /// Drop everything; in-flight loads finish but are not stored.
  void invalidate() {
    _generation++;
    _entries.clear();
    _inflight.clear();
  }

  int get length => _entries.length;
}
