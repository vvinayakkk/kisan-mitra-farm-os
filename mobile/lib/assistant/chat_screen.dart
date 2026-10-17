import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/language.dart';
import '../ui/kit.dart';
import '../utils/constants.dart';
import 'assistant_controller.dart';
import 'models.dart';
import 'widgets/composer.dart';
import 'widgets/message_view.dart';
import 'widgets/pending_card.dart';
import 'widgets/sheets.dart';

/// Feature chips from the original app, now pointing at the Farm OS screens.
/// The four things farmers reach for most; everything else is under "More".
const kMainChips = <(String, IconData, Color, String)>[
  ('fos.assistant.chip_mandi_rates', Icons.storefront_outlined, Color(0xFFF59E0B), '/markets'),
  ('fos.assistant.chip_weather', Icons.cloud_outlined, Color(0xFF0EA5E9), '/weather'),
  ('fos.assistant.chip_crop_doctor', Icons.healing_rounded, Color(0xFF10B981), '/crops'),
  ('fos.label.chip_my_tasks', Icons.calendar_month_outlined, Color(0xFF3B82F6), '/calendar'),
];

const kMoreChips = <(String, IconData, Color, String)>[
  ('fos.assistant.chip_farm_station', Icons.sensors_outlined, Color(0xFFE91E63), '/station'),
  ('fos.assistant.chip_schemes', Icons.account_balance_outlined, Color(0xFF9C27B0), '/schemes'),
  ('fos.assistant.chip_farm_notebook', Icons.menu_book_outlined, Color(0xFF795548), '/notebook'),
  ('fos.assistant.chip_farmer_exchange', Icons.handshake_outlined, Color(0xFF00BCD4), '/exchange'),
  ('fos.assistant.chip_saathi', Icons.spa_outlined, Color(0xFF16A34A), '/saathi'),
  ('fos.assistant.chip_profile', Icons.person_outlined, Color(0xFFFF5722), '/profile'),
];

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _composer = GlobalKey<ComposerState>();

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(assistantProvider);
    final controller = ref.read(assistantProvider.notifier);
    final latestAnswer = state.messages.lastWhere((m) => m.role == Role.assistant,
        orElse: () => const ChatMessage(id: '', role: Role.assistant));
    final items = <Widget>[
      for (final m in state.messages)
        MessageView(
          key: ValueKey(m.id),
          message: m,
          liveStatus: state.status,
          canRewrite: !state.busy &&
              state.pending == null &&
              m.id == latestAnswer.id &&
              m.status == 'completed' &&
              !m.id.startsWith('local-'),
          onRetry: state.busy ? null : () => controller.retryLast(),
        ),
      if (state.pending != null && !state.busy) PendingCard(pending: state.pending!),
      for (var i = 0; i < state.outbox.length; i++)
        _QueuedBubble(text: state.outbox[i], onRemove: () => controller.removeQueued(i)),
    ];
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_rounded),
          onPressed: () => context.canPop() ? context.pop() : context.go('/'),
        ),
        title: Text('chat.title'.tr()),
        actions: [
          IconButton(
            tooltip: 'fos.assistant.conversations'.tr(),
            icon: const Icon(Icons.history_rounded),
            onPressed: () => showHistorySheet(context),
          ),
          IconButton(
            tooltip: 'fos.assistant.new_chat'.tr(),
            icon: const Icon(Icons.refresh_rounded),
            onPressed: state.busy ? null : controller.newConversation,
          ),
        ],
      ),
      body: FarmBackground(
        child: Column(children: [
          if (state.error != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: ErrorView(state.error!, onRetry: state.ready ? controller.refresh : controller.load),
            ),
          if (state.recovering)
            const LinearProgressIndicator(minHeight: 2),
          Expanded(
            child: !state.ready && state.loading
                ? LoadingView('fos.assistant.opening_workspace'.tr())
                : state.messages.isEmpty && state.pending == null && state.outbox.isEmpty
                    ? _Welcome(onSkills: () => showCatalogSheet(context, onUseSkill: (skill) {
                        _composer.currentState?.setDraft('fos.assistant.use_skill_draft'.tr(namedArgs: {'name': skill.name}));
                      }))
                    : RefreshIndicator(
                        onRefresh: controller.refresh,
                        child: ListView.builder(
                          reverse: true,
                          padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
                          itemCount: items.length,
                          itemBuilder: (_, i) => items[items.length - 1 - i],
                        ),
                      ),
          ),
          Composer(key: _composer),
        ]),
      ),
    );
  }
}

/// Empty chat: the heading and one set of chips. Every feature lives in the chips.
class _Welcome extends StatelessWidget {
  const _Welcome({required this.onSkills});

  final VoidCallback onSkills;

  @override
  Widget build(BuildContext context) => Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text('chat.empty_title'.tr(),
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: inkColor(context))),
            const SizedBox(height: 20),
            Wrap(alignment: WrapAlignment.center, spacing: 10, runSpacing: 10, children: [
              for (final (label, icon, color, route) in kMainChips)
                OutlineChip(label: label.tr(), icon: icon, iconColor: color, onTap: () => context.push(route)),
              OutlineChip(
                label: 'fos.label.chip_more'.tr(),
                icon: Icons.apps_rounded,
                iconColor: AppColors.primary,
                onTap: () => _showMore(context, onSkills),
              ),
            ]),
          ]),
        ),
      );
}

/// A message typed without network, waiting to be sent.
class _QueuedBubble extends StatelessWidget {
  const _QueuedBubble({required this.text, required this.onRemove});

  final String text;
  final VoidCallback onRemove;

  @override
  Widget build(BuildContext context) => Align(
        alignment: Alignment.centerRight,
        child: Container(
          margin: const EdgeInsets.only(left: 48, top: 6, bottom: 6),
          padding: const EdgeInsets.fromLTRB(14, 10, 6, 6),
          decoration: BoxDecoration(
            color: AppColors.primary.withValues(alpha: 0.45),
            borderRadius: BorderRadius.circular(18).copyWith(bottomRight: const Radius.circular(4)),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Text(text, style: const TextStyle(color: Colors.white, fontSize: 15)),
            Row(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.schedule_rounded, size: 14, color: Colors.white),
              const SizedBox(width: 4),
              Text('fos.offline.waiting_to_send'.tr(), style: const TextStyle(color: Colors.white, fontSize: 12)),
              IconButton(
                tooltip: 'fos.offline.remove'.tr(),
                visualDensity: VisualDensity.compact,
                icon: const Icon(Icons.close_rounded, size: 16, color: Colors.white),
                onPressed: onRemove,
              ),
            ]),
          ]),
        ),
      );
}

void _showMore(BuildContext context, VoidCallback onSkills) {
  showModalBottomSheet<void>(
    context: context,
    builder: (sheet) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Wrap(alignment: WrapAlignment.center, spacing: 10, runSpacing: 10, children: [
          for (final (label, icon, color, route) in kMoreChips)
            OutlineChip(
              label: label.tr(),
              icon: icon,
              iconColor: color,
              onTap: () {
                Navigator.pop(sheet);
                context.push(route);
              },
            ),
          OutlineChip(
            label: 'fos.assistant.chip_skills'.tr(),
            icon: Icons.auto_awesome,
            iconColor: const Color(0xFF10B981),
            onTap: () {
              Navigator.pop(sheet);
              onSkills();
            },
          ),
          OutlineChip(
            label: 'language_select.title'.tr(),
            icon: Icons.translate_rounded,
            iconColor: const Color(0xFF673AB7),
            onTap: () {
              Navigator.pop(sheet);
              showLanguagePicker(context);
            },
          ),
        ]),
      ),
    ),
  );
}

Future<void> showLanguagePicker(BuildContext context) async {
  final container = ProviderScope.containerOf(context);
  final current = container.read(languageProvider).code;
  final picked = await showModalBottomSheet<String>(
    context: context,
    useSafeArea: true,
    builder: (c) => ListView(shrinkWrap: true, children: [
      ListTile(
        title: Text('fos.assistant.preferred_language'.tr(), style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text('fos.assistant.preferred_language_hint'.tr()),
      ),
      for (final (code, name) in kAppLanguages)
        ListTile(
          title: Text(name),
          trailing: code == current ? const Icon(Icons.check, color: AppColors.primary) : null,
          onTap: () => Navigator.pop(c, code),
        ),
    ]),
  );
  if (picked == null) return;
  await container.read(languageProvider.notifier).choose(picked);
  if (context.mounted && kUiLocales.contains(picked)) {
    await context.setLocale(Locale(picked));
  }
}
