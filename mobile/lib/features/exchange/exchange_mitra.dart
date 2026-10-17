import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api.dart';
import '../../core/session.dart';
import '../../ui/kit.dart';
import '../../ui/loader.dart';
import '../../utils/constants.dart';

const _intents = {
  'prepare_listing': ('What do you have or need?', 'I have a sprayer for two days. I need help with my harvest…'),
  'compare_matches': ('Find a fit', 'Which options fit my resource and exchange wishes?'),
  'draft_terms': ('Draft terms', 'Help me write terms for quantity, handover and transport…'),
  'review_exchange': ('Review this exchange', 'What is missing before we agree or hand over?'),
};

/// Exchange-specific assistant. It returns reviewable drafts only; nothing is
/// published, sent or agreed from here.
void showExchangeMitra(BuildContext context,
    {required String intent, String? listingId, String? conversationId, void Function(Map<String, dynamic> draft)? onDraft}) {
  showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    useSafeArea: true,
    builder: (_) => _ExchangeMitra(intent: intent, listingId: listingId, conversationId: conversationId, onDraft: onDraft),
  );
}

class _ExchangeMitra extends ConsumerStatefulWidget {
  const _ExchangeMitra({required this.intent, this.listingId, this.conversationId, this.onDraft});

  final String intent;
  final String? listingId;
  final String? conversationId;
  final void Function(Map<String, dynamic>)? onDraft;

  @override
  ConsumerState<_ExchangeMitra> createState() => _ExchangeMitraState();
}

class _ExchangeMitraState extends ConsumerState<_ExchangeMitra> {
  final _text = TextEditingController();
  final _turns = <String>[];
  Map<String, dynamic>? _result;
  String? _error;
  bool _busy = false;

  Future<void> _ask() async {
    final text = _text.text.trim();
    if (text.isEmpty) return;
    final brief = [..._turns, text].join('\nFarmer follow-up: ');
    if (brief.length > 4000) return setState(() => _error = 'Too long. Shorten or start over.');
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = asMap(await ref.read(apiProvider).post('/api/exchange/assist',
          timeout: const Duration(seconds: 60),
          body: {
            'intent': widget.intent,
            'message': brief,
            if (widget.listingId != null) 'listing_id': widget.listingId,
            if (widget.conversationId != null) 'conversation_id': widget.conversationId,
          }));
      setState(() {
        _turns.add(text);
        _result = r;
        _text.clear();
      });
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final (title, hint) = _intents[widget.intent]!;
    final draft = asMap(_result?['draft']);
    final questions = (_result?['questions'] as List? ?? const []).map((e) => '$e').toList();
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          if (_result != null) ...[
            MarkdownBody(data: str(_result!['answer'])),
            for (final q in questions) Text('• $q'),
            if (draft.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(border: Border.all(color: AppColors.warning), borderRadius: BorderRadius.circular(12)),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Tag('Draft · not saved', color: AppColors.warning),
                  const SizedBox(height: 6),
                  Text(draft['kind'] == 'terms'
                      ? str(draft['text'])
                      : asMap(draft['fields']).entries.map((e) => '${e.key.replaceAll('_', ' ')}: ${e.value}').join('\n')),
                  if (widget.onDraft != null)
                    FilledButton.tonal(
                      onPressed: () {
                        Navigator.pop(context);
                        widget.onDraft!(draft);
                      },
                      child: const Text('Review draft'),
                    ),
                ]),
              ),
            ],
            const Divider(),
          ],
          TextField(
            controller: _text,
            minLines: 2,
            maxLines: 5,
            decoration: InputDecoration(hintText: hint),
          ),
          if (_error != null) Text(_error!, style: const TextStyle(color: AppColors.error)),
          Row(children: [
            if (_turns.isNotEmpty)
              TextButton(onPressed: () => setState(() { _turns.clear(); _result = null; }), child: const Text('Start over')),
            const Spacer(),
            FilledButton(onPressed: _busy
                    ? null
                    : () {
                        HapticFeedback.selectionClick();
                        _ask();
                      },
                child: Text(_busy ? 'Thinking…' : 'Ask Mitra')),
          ]),
          Text('AI draft; nothing is sent without you.',
              style: TextStyle(fontSize: 11, color: mutedColor(context))),
        ]),
      ),
    );
  }
}
