import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'read_cache.dart';
import 'session.dart';

/// One bounded cache per session: a new sign-in gets a fresh, empty cache.
final workspaceCacheProvider = Provider<ReadCache>((ref) {
  ref.watch(authProvider.select((s) => s.session?.id));
  return ReadCache();
});

/// Cached GET through the session-bound client. Use for reads that many
/// screens share (market, schemes, weather). Writes call `invalidate()`.
extension CachedReads on WidgetRef {
  Future<dynamic> cachedGet(String path, {Map<String, Object?>? query}) {
    final key = '$path?${query?.entries.map((e) => '${e.key}=${e.value}').join('&') ?? ''}';
    return read(workspaceCacheProvider).read(key, () => read(apiProvider).get(path, query: query));
  }
}
