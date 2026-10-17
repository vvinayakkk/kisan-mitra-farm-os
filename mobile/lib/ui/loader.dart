import 'dart:async';
import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/offline.dart';

import '../core/api.dart';
import 'kit.dart';

/// Loads once, shows loading / error-with-retry / data. Call [LoaderState.reload]
/// (via a GlobalKey) after a write.
class Loader<T> extends ConsumerStatefulWidget {
  const Loader(
      {super.key, required this.load, required this.builder, this.loading});

  final Future<T> Function() load;
  final Widget Function(BuildContext context, T data) builder;
  final String? loading;

  @override
  ConsumerState<Loader<T>> createState() => LoaderState<T>();
}

class LoaderState<T> extends ConsumerState<Loader<T>> {
  T? _data;
  String? _error;
  bool _busy = true;
  int _generation = 0;
  Timer? _progressDelay;
  bool _showProgress = false;
  @override
  void dispose() {
    _progressDelay?.cancel();
    super.dispose();
  }

  @override
  void initState() {
    super.initState();
    reload();
  }

  Future<void> reload() async {
    final generation = ++_generation;
    _progressDelay?.cancel();
    _showProgress = false;
    _progressDelay = Timer(const Duration(milliseconds: 300), () {
      if (mounted && _busy) setState(() => _showProgress = true);
    });
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final data = await widget.load();
      if (!mounted || generation != _generation) return;
      setState(() {
        _data = data;
        _busy = false;
      });
    } catch (e) {
      if (!mounted || generation != _generation) return;
      setState(() {
        _error =
            e is ApiException ? e.message : 'fos.notebook.load_failed'.tr();
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(syncRevisionProvider, (_, __) => reload());
    if (_error != null && _data == null) {
      return ErrorView(_error!, onRetry: reload);
    }
    final data = _data;
    if (data == null) {
      return ContentSkeleton(
          label: widget.loading ?? 'fos.notebook.loading'.tr());
    }
    return Stack(children: [
      widget.builder(context, data),
      if (_busy && _showProgress)
        const Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: LinearProgressIndicator(minHeight: 2)),
      if (_error != null)
        Positioned(
            left: 8,
            right: 8,
            bottom: 8,
            child: Semantics(
                liveRegion: true,
                child: Material(
                    elevation: 2,
                    borderRadius: BorderRadius.circular(14),
                    color:
                        Theme.of(context).colorScheme.surfaceContainerHighest,
                    child: Padding(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 12, vertical: 4),
                        child: Row(children: [
                          const Icon(Icons.cloud_off_outlined, size: 20),
                          const SizedBox(width: 8),
                          const Expanded(
                              child: Text(
                                  'Could not refresh. Keeping your previous view.')),
                          TextButton(
                              onPressed: reload,
                              child: Text('fos.notebook.retry'.tr())),
                        ]))))),
    ]);
  }
}

/// Honest placeholders: no invented counts or values, and no shimmer motion.
class ContentSkeleton extends StatelessWidget {
  const ContentSkeleton({super.key, required this.label});
  final String label;
  @override
  Widget build(BuildContext context) => Semantics(
      label: label,
      liveRegion: true,
      child: ExcludeSemantics(
          child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final width in [0.55, 1.0, 0.8]) ...[
                      FractionallySizedBox(
                          widthFactor: width,
                          child: Container(
                              height: 22,
                              decoration: BoxDecoration(
                                  color: Theme.of(context)
                                      .colorScheme
                                      .onSurface
                                      .withValues(alpha: .07),
                                  borderRadius: BorderRadius.circular(8)))),
                      const SizedBox(height: 16),
                    ],
                    Text(label,
                        style: TextStyle(
                            color: mutedColor(context), fontSize: 12)),
                  ]))));
}

Map<String, dynamic> asMap(Object? v) =>
    v is Map ? v.map((k, v) => MapEntry('$k', v)) : <String, dynamic>{};
List<Map<String, dynamic>> asMaps(Object? v) =>
    v is List ? v.whereType<Map>().map(asMap).toList() : const [];
String str(Object? v, [String fallback = '']) =>
    v == null || '$v'.isEmpty ? fallback : '$v';
