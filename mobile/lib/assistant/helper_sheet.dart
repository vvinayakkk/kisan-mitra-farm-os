import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../ui/kit.dart';
import '../utils/constants.dart';
import 'assistant_controller.dart';
import 'models.dart';
import 'suggestions.dart';
import 'widgets/composer.dart';
import 'widgets/message_view.dart';
import 'widgets/pending_card.dart';

/// "A little help from Mitra" for one page: four focused prompts, the latest
/// reply, any question/approval card, and a composer. It shares the one
/// assistant conversation, so the full chat shows the same turns.
class HelperButton extends StatelessWidget {
  const HelperButton({super.key, required this.contextKey, this.runContext});

  final String contextKey;
  final RunContext? runContext;

  @override
  Widget build(BuildContext context) => FloatingActionButton.extended(
        heroTag: 'helper-$contextKey',
        backgroundColor: AppColors.primary,
        foregroundColor: Colors.white,
        onPressed: () => showHelperSheet(context, contextKey, runContext: runContext),
        icon: const Icon(Icons.eco),
        label: Text('fos.assistant.ask_mitra'.tr()),
      );
}

void showHelperSheet(BuildContext context, String contextKey, {RunContext? runContext}) {
  final run = runContext ?? RunContext(view: runView(contextKey));
  // Only turns started from this sheet belong here; the full chat keeps the rest.
  final startAt = ProviderScope.containerOf(context).read(assistantProvider).messages.length;
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (sheetContext) => Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(sheetContext).bottom),
      child: DraggableScrollableSheet(
        expand: false,
        initialChildSize: 0.6,
        maxChildSize: 0.95,
        builder: (context, scroll) => Consumer(builder: (context, ref, _) {
          final state = ref.watch(assistantProvider);
          final controller = ref.read(assistantProvider.notifier);
          final mine = state.messages.length > startAt ? state.messages.sublist(startAt) : const <ChatMessage>[];
          final last = mine.length > 2 ? mine.sublist(mine.length - 2) : mine;
          final idle = state.ready && !state.busy && state.pending == null;
          return Column(children: [
            Expanded(
              child: ListView(controller: scroll, padding: const EdgeInsets.all(16), children: [
                Row(children: [
                  const Icon(Icons.eco, color: AppColors.primary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text('fos.assistant.help_title'.tr(),
                        style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16, color: inkColor(context))),
                  ),
                  TextButton(
                    onPressed: () {
                      Navigator.pop(sheetContext);
                      context.push('/chat');
                    },
                    child: Text('fos.assistant.full_chat'.tr()),
                  ),
                ]),
                const SizedBox(height: 8),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  for (final (label, prompt) in kSuggestions[contextKey] ?? kSuggestions['assistant']!)
                    OutlineChip(
                      label: suggestionLabel(label),
                      icon: Icons.auto_awesome,
                      onTap: idle ? () => controller.send(prompt, context: run) : null,
                    ),
                ]),
                const SizedBox(height: 8),
                for (final m in last)
                  MessageView(message: m, liveStatus: state.status),
                if (state.pending != null && !state.busy) PendingCard(pending: state.pending!),
              ]),
            ),
            Composer(runContext: run),
          ]);
        }),
      ),
    ),
  );
}
