import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api.dart';
import '../../core/language.dart';
import '../../ui/kit.dart';
import '../../utils/constants.dart';
import '../../voice/speech.dart';
import '../assistant_controller.dart';
import '../models.dart';
import 'farm_result.dart';

class MessageView extends ConsumerWidget {
  const MessageView(
      {super.key,
      required this.message,
      this.liveStatus = '',
      this.canRewrite = false,
      this.onRetry});

  final ChatMessage message;
  final String liveStatus;
  final bool canRewrite;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final user = message.role == Role.user;
    final ink = inkColor(context);
    if (user) {
      return Align(
        alignment: Alignment.centerRight,
        child: Container(
          margin: const EdgeInsets.only(left: 48, top: 6, bottom: 6),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          decoration: BoxDecoration(
            color: AppColors.primary,
            borderRadius: BorderRadius.circular(18)
                .copyWith(bottomRight: const Radius.circular(4)),
          ),
          child: SelectableText(message.text,
              style: const TextStyle(color: Colors.white, fontSize: 15)),
        ),
      );
    }
    final empty = message.text.isEmpty &&
        message.activities.isEmpty &&
        message.error == null &&
        !message.working;
    // A paused turn's content is the card below; a stopped turn says so.
    if (empty && message.status != 'stopped') return const SizedBox.shrink();
    if (empty) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 16),
        child: Text('fos.assistant.stopped_no_answer'.tr(),
            style: TextStyle(fontSize: 12.5, color: mutedColor(context))),
      );
    }
    return Padding(
      padding: const EdgeInsets.only(right: 8, top: 6, bottom: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const CircleAvatar(
                radius: 10,
                backgroundColor: AppColors.primary,
                child: Icon(Icons.eco, size: 12, color: Colors.white)),
            const SizedBox(width: 6),
            Text('Kisan Mitra',
                style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: mutedColor(context))),
          ]),
          if (message.activities.isNotEmpty) ActivityPanel(message: message),
          if (message.text.isNotEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(0, 14, 0, 10),
              child: SelectionArea(child: MarkdownBody(
                data: message.text,
                selectable: false,
                styleSheet:
                    MarkdownStyleSheet.fromTheme(Theme.of(context)).copyWith(
                  p: TextStyle(fontSize: 15, height: 1.65, color: ink),
                ),
                sizedImageBuilder: (_) => const SizedBox.shrink(),
                onTapLink: (_, href, __) {
                  final uri = Uri.tryParse(href ?? '');
                  if (uri != null &&
                      (uri.scheme == 'https' || uri.scheme == 'http')) {
                    launchUrl(uri, mode: LaunchMode.externalApplication);
                  }
                },
              )),
            ),
          if (message.text.isNotEmpty && !message.working)
            AnswerActions(message: message, canRewrite: canRewrite),
          for (final a in message.activities)
            if (a.status == ActivityStatus.done && a.result.isNotEmpty)
              FarmResult(a.result,
                  onRevise: (artifact) => _revise(ref, artifact)),
          if (message.error != null)
            ErrorView(message.error!,
                onRetry:
                    message.status == 'error' || message.status == 'stopped'
                        ? onRetry
                        : null),
          if (message.working &&
              message.text.isEmpty &&
              message.activities.isEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Row(children: [
                const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2)),
                const SizedBox(width: 8),
                Text(
                    liveStatus.isEmpty
                        ? 'fos.assistant.getting_started'.tr()
                        : liveStatus,
                    style: TextStyle(color: mutedColor(context))),
              ]),
            ),
        ],
      ),
    );
  }

  void _revise(WidgetRef ref, Artifact a) =>
      ref.read(assistantProvider.notifier).send('fos.assistant.revise_prompt'
          .tr(namedArgs: {'title': a.title, 'id': a.fileId}));
}

/// Collapsible list of the run's persisted tool/skill activity. Rows exist
/// only because the server emitted them; nothing here is simulated.
class ActivityPanel extends StatefulWidget {
  const ActivityPanel({super.key, required this.message});

  final ChatMessage message;

  @override
  State<ActivityPanel> createState() => _ActivityPanelState();
}

class _ActivityPanelState extends State<ActivityPanel> {
  bool? _open;

  @override
  Widget build(BuildContext context) {
    final m = widget.message;
    final open = _open ?? m.working;
    final n = m.activities.length;
    final ink = inkColor(context);
    return Padding(
      padding: const EdgeInsets.only(top: 6, bottom: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: () => setState(() => _open = !open),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 16),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                m.working
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(strokeWidth: 2))
                    : Icon(Icons.check_circle_outline,
                        size: 16, color: accentColor(context)),
                const SizedBox(width: 6),
                Text(
                    m.working
                        ? 'fos.assistant.working_request'.tr()
                        : n == 1
                            ? 'fos.assistant.one_step'.tr()
                            : 'fos.assistant.n_steps'
                                .tr(namedArgs: {'count': '$n'}),
                    style: TextStyle(
                        fontSize: 13, fontWeight: FontWeight.w600, color: ink)),
                Icon(open ? Icons.expand_less : Icons.expand_more,
                    size: 18, color: ink),
              ]),
            ),
          ),
          if (open)
            for (final a in m.activities) _row(context, a, m.working),
        ],
      ),
    );
  }

  Widget _row(BuildContext context, Activity a, bool working) {
    // A run that ended while a call was open: say so instead of spinning.
    final orphaned = a.status == ActivityStatus.running && !working;
    final icon = switch (a.status) {
      _ when orphaned => const Icon(Icons.remove_circle_outline,
          size: 16, color: AppColors.textMuted),
      ActivityStatus.running => const SizedBox(
          width: 14,
          height: 14,
          child: CircularProgressIndicator(strokeWidth: 2)),
      ActivityStatus.error =>
        const Icon(Icons.error_outline, size: 16, color: AppColors.error),
      ActivityStatus.done =>
        Icon(Icons.check, size: 16, color: accentColor(context)),
    };
    final detail = orphaned ? 'fos.assistant.not_finished'.tr() : a.outcome;
    final time = a.elapsedMs == null
        ? ''
        : ' · ${(a.elapsedMs! / 1000).toStringAsFixed(1)}s';
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 6),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(padding: const EdgeInsets.only(top: 2), child: icon),
        const SizedBox(width: 8),
        Expanded(
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(a.label,
                style: TextStyle(fontSize: 13, color: inkColor(context))),
            Text('$detail$time',
                style: TextStyle(fontSize: 11.5, color: mutedColor(context))),
          ]),
        ),
      ]),
    );
  }
}

/// Copy, share, listen, rewrite. Ratings stay local, like the web.
class AnswerActions extends ConsumerStatefulWidget {
  const AnswerActions(
      {super.key, required this.message, required this.canRewrite});

  final ChatMessage message;
  final bool canRewrite;

  @override
  ConsumerState<AnswerActions> createState() => _AnswerActionsState();
}

class _AnswerActionsState extends ConsumerState<AnswerActions> {
  bool _speaking = false;
  bool _rewriting = false;
  String? _alternative;

  Future<void> _speak() async {
    final speech = ref.read(speechProvider);
    if (_speaking) {
      await speech.stopSpeaking();
      return;
    }
    setState(() => _speaking = true);
    try {
      final text = speakableText(widget.message.text);
      await speech.speak(
          text, speechLanguageFor(text, ref.read(languageProvider).code));
    } on ApiException catch (e) {
      if (mounted) showNotice(context, e.message);
    } finally {
      if (mounted) setState(() => _speaking = false);
    }
  }

  Future<void> _rewrite() async {
    setState(() => _rewriting = true);
    try {
      final text =
          await ref.read(assistantProvider.notifier).rewrite(widget.message);
      setState(() => _alternative = text);
    } on ApiException catch (e) {
      if (mounted) showNotice(context, e.message);
    } finally {
      if (mounted) setState(() => _rewriting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final muted = mutedColor(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(crossAxisAlignment: WrapCrossAlignment.center, children: [
          IconButton(
            tooltip: 'fos.assistant.copy_answer'.tr(),
            visualDensity: VisualDensity.standard,
            icon: Icon(Icons.copy_rounded, size: 18, color: muted),
            onPressed: () async {
              await Clipboard.setData(ClipboardData(text: widget.message.text));
              if (context.mounted) {
                showNotice(context, 'fos.assistant.answer_copied'.tr());
              }
            },
          ),
          IconButton(
            tooltip: 'fos.assistant.share_answer'.tr(),
            visualDensity: VisualDensity.standard,
            icon: Icon(Icons.share_outlined, size: 18, color: muted),
            onPressed: () => SharePlus.instance.share(ShareParams(
                text: widget.message.text,
                subject: 'fos.assistant.share_subject'.tr())),
          ),
          IconButton(
            tooltip: _speaking
                ? 'fos.assistant.stop_reading'.tr()
                : 'fos.assistant.read_aloud'.tr(),
            visualDensity: VisualDensity.standard,
            icon: Icon(
                _speaking
                    ? Icons.stop_circle_outlined
                    : Icons.volume_up_outlined,
                size: 18,
                color: muted),
            onPressed: _speak,
          ),
          if (widget.canRewrite)
            TextButton.icon(
              onPressed: _rewriting ? null : _rewrite,
              icon: _rewriting
                  ? const SizedBox(
                      width: 14,
                      height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.autorenew, size: 16),
              label: Text('fos.assistant.explain_differently'.tr()),
            ),
        ]),
        if (_alternative != null)
          FarmCard(
            color: AppColors.primarySurface
                .withValues(alpha: context.isDark ? 0.15 : 0.9),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Tag('fos.assistant.alt_explanation'.tr()),
              const SizedBox(height: 6),
              MarkdownBody(data: _alternative!, selectable: true),
            ]),
          ),
      ],
    );
  }
}
