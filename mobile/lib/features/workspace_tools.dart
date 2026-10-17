import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/session.dart';
import '../core/workspace_cache.dart';
import '../ui/loader.dart';

/// Read-only assistant tools that feature screens share with chat
/// (`POST /api/assistant/sessions/{sid}/inspect/{tool}`).
class WorkspaceTools {
  WorkspaceTools(this._ref);

  final Ref _ref;

  static const _cached = {'market_prices', 'market_trend', 'scheme_search'};

  Future<Map<String, dynamic>> inspect(String tool, Map<String, Object?> args) async {
    final api = _ref.read(apiProvider);
    final session = api.session;
    if (session == null) throw StateError('No session');
    Future<Map<String, dynamic>> load() async => asMap(await api.post(
          '/api/assistant/sessions/${session.id}/inspect/$tool',
          body: args,
          timeout: Duration(seconds: tool == 'diagnose_crop' ? 95 : 25),
          saveCopy: _cached.contains(tool),
        ));
    if (!_cached.contains(tool)) return load();
    final key = 'inspect:$tool:${jsonEncode(Map.fromEntries(args.entries.toList()..sort((a, b) => a.key.compareTo(b.key))))}';
    return _ref.read(workspaceCacheProvider).read(key, load);
  }
}

final workspaceToolsProvider = Provider<WorkspaceTools>((ref) {
  ref.watch(apiProvider);
  return WorkspaceTools(ref);
});
