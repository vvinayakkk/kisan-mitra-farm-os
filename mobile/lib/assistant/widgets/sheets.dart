import 'package:easy_localization/easy_localization.dart';
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
              Tab(text: 'fos.assistant.skills_tab'.tr(namedArgs: {'count': '${catalog.skills.length}'})),
              Tab(text: 'fos.assistant.tools_tab'.tr(namedArgs: {'count': '${catalog.tools.length}'})),
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
    if (entries.isEmpty) return EmptyView(title: 'fos.assistant.catalog_loading'.tr());
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
            skills ? e.description : (e.approval ? 'fos.assistant.tool_review_short'.tr() : 'fos.assistant.tool_reads_only'.tr()),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          trailing: e.approval ? Tag('fos.assistant.review_tag'.tr(), color: AppColors.warning) : null,
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          children: [
            Text(e.description),
            if (!skills)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(
                  e.approval
                      ? 'fos.assistant.tool_review_long'.tr()
                      : 'fos.assistant.tool_runs_long'.tr(),
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
                  child: Text('fos.assistant.use_skill'.tr()),
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
            title: Text('fos.assistant.conversations'.tr(), style: const TextStyle(fontWeight: FontWeight.w700)),
            trailing: FilledButton.icon(
              onPressed: state.busy
                  ? null
                  : () async {
                      Navigator.pop(context);
                      await controller.newConversation();
                    },
              icon: const Icon(Icons.add),
              label: Text('fos.assistant.new_chat'.tr()),
            ),
          ),
          if (state.conversations.isEmpty)
            EmptyView(
                title: 'fos.assistant.no_conversations'.tr(),
                detail: 'fos.assistant.no_conversations_hint'.tr())
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
