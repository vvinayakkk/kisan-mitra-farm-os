import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api.dart';
import '../../core/session.dart';
import '../../ui/kit.dart';
import '../../ui/labels.dart';
import '../../ui/loader.dart';
import '../../utils/constants.dart';

const _intents = {
  'prepare_listing': ('fos.market.intent_prepare_t', 'fos.market.intent_prepare_h'),
  'compare_matches': ('fos.market.intent_compare_t', 'fos.market.intent_compare_h'),
  'draft_terms': ('fos.market.intent_terms_t', 'fos.market.intent_terms_h'),
  'review_exchange': ('fos.market.intent_review_t', 'fos.market.intent_review_h'),
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

const _fieldKeys = {
  'kind': 'fos.market.i_am',
  'category': 'fos.market.category',
  'title': 'fos.market.f_title',
  'description': 'fos.market.f_description',
  'quantity': 'fos.market.f_quantity',
  'unit': 'fos.market.f_unit',
  'state': 'fos.market.f_state',
  'district': 'fos.market.district',
  'available_on': 'fos.market.available_from',
  'exchange_for': 'fos.market.in_exchange',
};

String _field(MapEntry<String, dynamic> e) {
  final label = _fieldKeys[e.key]?.tr() ?? humanize(e.key);
  final v = e.value;
  final value = switch (e.key) {
    'kind' => (v == 'request' ? 'fos.market.looking_for' : 'fos.market.offering').tr(),
    'category' => ({'equipment': 'fos.market.cat_equipment', 'labour': 'fos.market.cat_labour', 'transport': 'fos.market.cat_transport', 'produce': 'fos.market.cat_produce'}['$v']?.tr() ?? humanize('$v')),
    'available_on' => displayDate('$v'),
    'quantity' => qty(v),
    _ => phrase(v),
  };
  return '$label: $value';
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
    if (brief.length > 4000) return setState(() => _error = 'fos.market.too_long'.tr().tr());
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
    final (titleKey, hintKey) = _intents[widget.intent]!;
    final title = titleKey.tr();
    final hint = hintKey.tr();
    final draft = asMap(_result?['draft']);
    final questions = (_result?['questions'] as List? ?? const []).map((e) => '$e').toList();
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title, style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: inkColor(context))),
          const SizedBox(height: 8),
          if (_result != null) ...[
            MarkdownBody(data: str(_result!['answer'])),
            for (final q in questions) Text('• $q', style: TextStyle(color: inkColor(context))),
            if (draft.isNotEmpty) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(border: Border.all(color: AppColors.warning), borderRadius: BorderRadius.circular(12)),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Tag('fos.market.draft_not_saved'.tr(), color: AppColors.warning),
                  const SizedBox(height: 6),
                  Text(
                      draft['kind'] == 'terms'
                          ? str(draft['text'])
                          : asMap(draft['fields']).entries.where((e) => str(e.value).isNotEmpty).map(_field).join('\n'),
                      style: TextStyle(fontSize: 14, color: inkColor(context))),
                  if (widget.onDraft != null)
                    FilledButton.tonal(
                      onPressed: () {
                        Navigator.pop(context);
                        widget.onDraft!(draft);
                      },
                      child: Text('fos.market.review_draft'.tr()),
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
              TextButton(onPressed: () => setState(() { _turns.clear(); _result = null; }), child: Text('fos.market.start_over'.tr())),
            const Spacer(),
            FilledButton(onPressed: _busy
                    ? null
                    : () {
                        HapticFeedback.selectionClick();
                        _ask();
                      },
                child: Text(_busy ? 'fos.market.thinking'.tr() : 'fos.market.ask_mitra'.tr())),
          ]),
          Text('fos.market.ai_draft_note'.tr(),
              style: TextStyle(fontSize: 12, color: mutedColor(context))),
        ]),
      ),
    );
  }
}
