import 'dart:async';
import '../assistant/assistant_controller.dart';
import '../router.dart';
import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../core/offline.dart';
import '../core/session.dart';
import 'kit.dart';

final _live = ValueNotifier<DateTime?>(null);

/// App-wide strip above every screen: no network, or a screen is showing a
/// saved copy. While it shows, it takes the status-bar inset from the page.
class OfflineFrame extends ConsumerStatefulWidget {
  const OfflineFrame({super.key, required this.child});

  final Widget child;

  @override
  ConsumerState<OfflineFrame> createState() => _OfflineFrameState();
}

class _OfflineFrameState extends ConsumerState<OfflineFrame> with WidgetsBindingObserver {
  Timer? _retry;
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _retry = Timer.periodic(const Duration(seconds: 30), (_) {
      if (WidgetsBinding.instance.lifecycleState != AppLifecycleState.resumed ||
          !ref.read(authProvider).isAuthenticated) { return; }
      final state = ref.read(assistantProvider);
      if (!state.ready || state.outbox.isNotEmpty || ref.read(offlineStoreProvider)?.servedSavedAt.value != null) _sync();
    });
  }
  Future<void> _sync() async {
    if (!mounted || !ref.read(authProvider).isAuthenticated || ref.read(offlineProvider).value == true) return;
    final ok = await ref.read(assistantProvider.notifier).reconnect();
    if (ok && mounted) ref.read(syncRevisionProvider.notifier).state++;
  }
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _sync();
  }
  @override
  void dispose() {
    _retry?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }
  @override
  Widget build(BuildContext context) {
    ref.listen(offlineProvider, (before, after) {
      if (before?.value == true && after.value == false) _sync();
    });
    final signedIn = ref.watch(authProvider.select((s) => s.isAuthenticated));
    final state = signedIn ? ref.watch(assistantProvider) : const AssistantState();
    final offline = ref.watch(offlineProvider).value ?? false;
    final store = ref.watch(offlineStoreProvider);
    return ValueListenableBuilder<DateTime?>(
      valueListenable: store?.servedSavedAt ?? _live,
      builder: (context, savedAt, _) {
        if (!offline && savedAt == null && state.outbox.isEmpty && !state.syncing) return widget.child;
        final text = state.syncing ? 'Checking connection and syncing…'
            : state.outboxNeedsReview ? 'Send interrupted. Check the chat before retrying.'
            : state.outbox.isNotEmpty ? '${state.outbox.length} message(s) waiting to sync${offline ? ' · offline' : ''}'
            : savedAt != null
            ? 'fos.offline.showing_saved'.tr(namedArgs: {'time': displayDate(savedAt.toIso8601String(), withTime: true)})
            : 'fos.offline.no_network'.tr();
        final banner = Material(
          color: const Color(0xFFF0E8D8),
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
                if (signedIn && !state.syncing)
                  TextButton(onPressed: state.outboxNeedsReview ? () => ref.read(routerProvider).push('/chat') : () => _sync(),
                    child: Text(state.outboxNeedsReview ? 'Review' : 'Retry', style: const TextStyle(color: Colors.black87))),
              ]),
            ),
          ),
        );
        return Column(children: [
          banner,
          Expanded(child: MediaQuery.removePadding(context: context, removeTop: true, child: widget.child)),
        ]);
      },
    );
  }
}
