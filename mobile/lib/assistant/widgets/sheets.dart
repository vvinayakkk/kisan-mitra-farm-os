import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../ui/kit.dart';
import '../../utils/constants.dart';
import '../assistant_controller.dart';
import '../models.dart';

/// Skills and tools exactly as the server's catalog describes them.
void showCatalogSheet(BuildContext context, {void Function(CatalogEntry skill)? onUseSkill}) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (_) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.75,
      builder: (context, scroll) => DefaultTabController(
        length: 2,
        child: Consumer(builder: (context, ref, _) {
          final catalog = ref.watch(assistantProvider.select((s) => s.catalog));
          return Column(children: [
            const SizedBox(height: 8),
            TabBar(tabs: [
              Tab(text: 'Skills · ${catalog.skills.length}'),
              Tab(text: 'Tools · ${catalog.tools.length}'),
            ]),
            Expanded(
              child: TabBarView(children: [
                _CatalogList(entries: catalog.skills, scroll: scroll, onUse: onUseSkill, skills: true),
                _CatalogList(entries: catalog.tools, scroll: scroll, skills: false),
              ]),
            ),
          ]);
        }),
      ),
    ),
  );
}

class _CatalogList extends StatelessWidget {
  const _CatalogList({required this.entries, required this.scroll, required this.skills, this.onUse});

  final List<CatalogEntry> entries;
  final ScrollController scroll;
  final bool skills;
  final void Function(CatalogEntry)? onUse;

  @override
  Widget build(BuildContext context) {
    if (entries.isEmpty) return const EmptyView(title: 'The catalog is still loading.');
    return ListView.separated(
      controller: scroll,
      padding: const EdgeInsets.all(12),
      itemCount: entries.length,
      separatorBuilder: (_, __) => const Divider(height: 1),
      itemBuilder: (context, i) {
        final e = entries[i];
        return ExpansionTile(
          shape: const Border(),
          title: Text(e.name, style: const TextStyle(fontWeight: FontWeight.w600)),
          subtitle: Text(
            skills ? e.description : (e.approval ? 'You review before anything is saved' : 'Reads or prepares only'),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          trailing: e.approval ? const Tag('Review', color: AppColors.warning) : null,
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          children: [
            Text(e.description),
            if (!skills)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  e.approval
                      ? 'This tool pauses with a review card. Nothing changes until you approve it.'
                      : 'This tool runs when needed and reports its actual result in the conversation.',
                  style: TextStyle(fontSize: 12, color: mutedColor(context)),
                ),
              ),
            if (skills && onUse != null)
              Align(
                alignment: Alignment.centerRight,
                child: TextButton(
                  onPressed: () {
                    Navigator.pop(context);
                    onUse!(e);
                  },
                  child: const Text('Use this skill'),
                ),
              ),
          ],
        );
      },
    );
  }
}

/// Earlier conversations stored server-side for this farmer.
void showHistorySheet(BuildContext context) {
  showModalBottomSheet<void>(
    context: context,
    useSafeArea: true,
    isScrollControlled: true,
    builder: (_) => Consumer(builder: (context, ref, _) {
      final state = ref.watch(assistantProvider);
      final controller = ref.read(assistantProvider.notifier);
      return ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.7),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(
            title: const Text('Conversations', style: TextStyle(fontWeight: FontWeight.w700)),
            trailing: FilledButton.icon(
              onPressed: state.busy
                  ? null
                  : () async {
                      Navigator.pop(context);
                      await controller.newConversation();
                    },
              icon: const Icon(Icons.add),
              label: const Text('New chat'),
            ),
          ),
          if (state.conversations.isEmpty)
            const EmptyView(title: 'No earlier conversations yet.', detail: 'Starting a new chat keeps this one here.')
          else
            Flexible(
              child: ListView(shrinkWrap: true, children: [
                for (final c in state.conversations)
                  ListTile(
                    leading: const Icon(Icons.chat_bubble_outline),
                    title: Text(c.title, maxLines: 1, overflow: TextOverflow.ellipsis),
                    subtitle: Text(displayDate(c.createdAt, withTime: true)),
                    enabled: !state.busy,
                    onTap: () async {
                      Navigator.pop(context);
                      await controller.restoreConversation(c.id);
                    },
                  ),
              ]),
            ),
          const SizedBox(height: 12),
        ]),
      );
    }),
  );
}
