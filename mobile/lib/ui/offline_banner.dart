import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/offline.dart';
import '../core/session.dart';
import '../utils/constants.dart';
import 'kit.dart';

final _live = ValueNotifier<DateTime?>(null);

/// App-wide strip above every screen: no network, or a screen is showing a
/// saved copy. While it shows, it takes the status-bar inset from the page.
class OfflineFrame extends ConsumerWidget {
  const OfflineFrame({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final offline = ref.watch(offlineProvider).value ?? false;
    final store = ref.watch(offlineStoreProvider);
    return ValueListenableBuilder<DateTime?>(
      valueListenable: store?.servedSavedAt ?? _live,
      builder: (context, savedAt, _) {
        if (!offline && savedAt == null) return child;
        final text = savedAt != null
            ? 'fos.offline.showing_saved'.tr(namedArgs: {'time': displayDate(savedAt.toIso8601String(), withTime: true)})
            : 'fos.offline.no_network'.tr();
        final banner = Material(
          color: AppColors.warning,
          child: SafeArea(
            bottom: false,
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
              child: Row(children: [
                const Icon(Icons.cloud_off_rounded, size: 18, color: Colors.black87),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(text,
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.black87)),
                ),
              ]),
            ),
          ),
        );
        return Column(children: [
          banner,
          Expanded(child: MediaQuery.removePadding(context: context, removeTop: true, child: child)),
        ]);
      },
    );
  }
}
