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
const kFeatureChips = <(String, IconData, Color, String)>[
  ('Calendar', Icons.calendar_month_outlined, Color(0xFF3B82F6), '/calendar'),
  ('Crop Doctor', Icons.healing_rounded, Color(0xFF10B981), '/crops'),
  ('Mandi rates', Icons.storefront_outlined, Color(0xFFF59E0B), '/markets'),
  ('Weather', Icons.cloud_outlined, Color(0xFF0EA5E9), '/weather'),
  ('Farm station', Icons.sensors_outlined, Color(0xFFE91E63), '/station'),
  ('Schemes', Icons.account_balance_outlined, Color(0xFF9C27B0), '/schemes'),
  ('Farm notebook', Icons.menu_book_outlined, Color(0xFF795548), '/notebook'),
  ('Farmer exchange', Icons.handshake_outlined, Color(0xFF00BCD4), '/exchange'),
  ('Saathi', Icons.spa_outlined, Color(0xFF16A34A), '/saathi'),
  ('Profile', Icons.person_outlined, Color(0xFFFF5722), '/profile'),
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
            tooltip: 'Conversations',
            icon: const Icon(Icons.history_rounded),
            onPressed: () => showHistorySheet(context),
          ),
          IconButton(
            tooltip: 'New chat',
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
                ? const LoadingView('Opening your farm workspace…')
                : state.messages.isEmpty && state.pending == null
                    ? _Welcome(onSkills: () => showCatalogSheet(context, onUseSkill: (skill) {
                        _composer.currentState?.setDraft('Use the ${skill.name} skill: ');
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
              for (final (label, icon, color, route) in kFeatureChips)
                OutlineChip(label: label, icon: icon, iconColor: color, onTap: () => context.push(route)),
              OutlineChip(label: 'Skills', icon: Icons.auto_awesome, iconColor: const Color(0xFF10B981), onTap: onSkills),
              Builder(
                builder: (chipContext) => OutlineChip(
                  label: 'language_select.title'.tr(),
                  icon: Icons.translate_rounded,
                  iconColor: const Color(0xFF673AB7),
                  onTap: () => showLanguagePicker(chipContext),
                ),
              ),
            ]),
          ]),
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
      const ListTile(
        title: Text('Preferred language', style: TextStyle(fontWeight: FontWeight.w700)),
        subtitle: Text('Mitra answers in the language you write or speak. This is the fallback and voice language.'),
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
