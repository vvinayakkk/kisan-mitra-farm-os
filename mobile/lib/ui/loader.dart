import 'package:flutter/material.dart';

import '../core/api.dart';
import 'kit.dart';

/// Loads once, shows loading / error-with-retry / data. Call [LoaderState.reload]
/// (via a GlobalKey) after a write.
class Loader<T> extends StatefulWidget {
  const Loader({super.key, required this.load, required this.builder, this.loading = 'Loading…'});

  final Future<T> Function() load;
  final Widget Function(BuildContext context, T data) builder;
  final String loading;

  @override
  State<Loader<T>> createState() => LoaderState<T>();
}

class LoaderState<T> extends State<Loader<T>> {
  T? _data;
  String? _error;
  bool _busy = true;
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    reload();
  }

  Future<void> reload() async {
    final generation = ++_generation;
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
        _error = e is ApiException ? e.message : 'This could not be loaded. Please retry.';
        _busy = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_error != null) return ErrorView(_error!, onRetry: reload);
    final data = _data;
    if (data == null) return LoadingView(widget.loading);
    return Stack(children: [
      widget.builder(context, data),
      if (_busy) const Positioned(top: 0, left: 0, right: 0, child: LinearProgressIndicator(minHeight: 2)),
    ]);
  }
}

Map<String, dynamic> asMap(Object? v) => v is Map ? v.map((k, v) => MapEntry('$k', v)) : <String, dynamic>{};
List<Map<String, dynamic>> asMaps(Object? v) => v is List ? v.whereType<Map>().map(asMap).toList() : const [];
String str(Object? v, [String fallback = '']) => v == null || '$v'.isEmpty ? fallback : '$v';
