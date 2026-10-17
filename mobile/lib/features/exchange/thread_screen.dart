import 'package:easy_localization/easy_localization.dart';
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api.dart';
import '../../core/ids.dart';
import '../../core/session.dart';
import '../../ui/kit.dart';
import '../../ui/labels.dart';
import '../../ui/loader.dart';
import '../../utils/constants.dart';
import 'exchange_mitra.dart';
import 'exchange_screen.dart';

const _closed = {'completed', 'cancelled', 'disputed'};
const _trail = ['open', 'negotiating', 'agreed', 'handover', 'completed'];
const _actionText = {
  'propose': 'fos.market.act_propose',
  'accept': 'fos.market.act_accept',
  'handover': 'fos.market.act_handover',
  'complete': 'fos.market.act_complete',
  'dispute': 'fos.market.act_dispute',
  'cancel': 'fos.market.act_cancel',
};

/// One private exchange conversation: messages (polled) and the agreement
/// trail. Every step records what a participant reports.
class ThreadScreen extends ConsumerStatefulWidget {
  const ThreadScreen({super.key, required this.threadId});

  final String threadId;

  @override
  ConsumerState<ThreadScreen> createState() => _ThreadScreenState();
}

class _ThreadScreenState extends ConsumerState<ThreadScreen> {
  Map<String, dynamic>? _thread;
  final _messages = <int, Map<String, dynamic>>{};
  String? _error;
  Timer? _poll;
  final _text = TextEditingController();
  final _keys = IdempotencyKeys();
  bool _sending = false;

  ApiClient get _api => ref.read(apiProvider);
  String get _path => '/api/exchange/conversations/${widget.threadId}';

  @override
  void initState() {
    super.initState();
    _loadAll();
    _poll = Timer.periodic(const Duration(seconds: 7), (_) => _loadNew());
  }

  @override
  void dispose() {
    _poll?.cancel();
    _text.dispose();
    super.dispose();
  }

  void _merge(List<Map<String, dynamic>> items) {
    for (final m in items) {
      final seq = (m['sequence'] as num?)?.toInt();
      if (seq != null) _messages[seq] = m;
    }
    while (_messages.length > 300) {
      _messages.remove(_messages.keys.reduce((a, b) => a < b ? a : b));
    }
  }

  Future<void> _loadAll() async {
    try {
      final d = asMap(await _api.get(_path));
      if (!mounted) return;
      setState(() {
        _thread = asMap(d['thread']);
        _merge(asMaps(d['messages']));
        _error = null;
      });
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  Future<void> _loadNew() async {
    if (_thread == null) return;
    try {
      final after = _messages.isEmpty ? 0 : _messages.keys.reduce((a, b) => a > b ? a : b);
      final r = await Future.wait([
        _api.get('$_path/messages', query: {'after': after}),
        _api.get(_path, query: {'include_messages': false}),
      ]);
      if (!mounted) return;
      setState(() {
        _merge(asMaps(asMap(r[0])['items']));
        _thread = asMap(asMap(r[1])['thread']);
      });
    } catch (_) {
      // Polling is best-effort; the next tick retries.
    }
  }

  Future<void> _send() async {
    final text = _text.text.trim();
    if (text.isEmpty) return;
    final signature = '${widget.threadId}:$text';
    setState(() => _sending = true);
    try {
      final m = asMap(await _api.post('$_path/messages', body: {'text': text, 'client_key': _keys.forOperation(signature)}));
      _keys.succeeded(signature);
      _text.clear();
      setState(() => _merge([m]));
    } on ApiException catch (e) {
      if (mounted) showNotice(context, e.message);
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<void> _act(String action, {String? initialTerms}) async {
    final t = _thread!;
    final terms = TextEditingController(text: initialTerms ?? '');
    final needsTerms = action == 'propose' || action == 'dispute';
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => StatefulBuilder(builder: (c, set) => AlertDialog(
            title: Text('fos.market.confirm_step'.tr()),
            content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(_actionText[action]!.tr()),
              if (action == 'accept' && asMap(t['proposal'])['terms'] != null) ...[
                const SizedBox(height: 8),
                Text('fos.market.terms_line'.tr(namedArgs: {'text': '${asMap(t['proposal'])['terms']}'}), style: const TextStyle(fontWeight: FontWeight.w600)),
              ],
              if (needsTerms)
                TextField(
                  controller: terms,
                  maxLines: 4,
                  maxLength: 4000,
                  onChanged: (_) => set(() {}),
                  decoration: InputDecoration(labelText: action == 'propose' ? 'fos.market.terms'.tr() : 'fos.market.what_went_wrong'.tr()),
                ),
              if (action == 'propose')
                TextButton.icon(
                  onPressed: () => showExchangeMitra(c,
                      intent: 'draft_terms',
                      conversationId: widget.threadId,
                      onDraft: (d) => set(() => terms.text = str(d['text'], terms.text))),
                  icon: const Icon(Icons.auto_awesome, size: 16),
                  label: Text('fos.market.draft_with_mitra'.tr()),
                ),
            ]),
            actions: [
              TextButton(onPressed: () => Navigator.pop(c, false), child: Text('fos.market.back'.tr())),
              FilledButton(
                onPressed: needsTerms && terms.text.trim().length < 2 ? null : () => Navigator.pop(c, true),
                child: Text('fos.market.confirm'.tr()),
              ),
            ],
          )),
    );
    if (ok != true) return;
    final body = {
      'action': action,
      'row_version': t['row_version'],
      if (needsTerms) 'terms': terms.text.trim(),
    };
    final signature = '${widget.threadId}:${t['row_version']}:$action:${body['terms'] ?? ''}';
    try {
      final r = asMap(await _api.post('$_path/actions', body: {...body, 'client_key': _keys.forOperation(signature)}));
      _keys.succeeded(signature);
      if (!mounted) return;
      setState(() => _thread = {..._thread!, ...r});
      if (str(r['action_note']).isNotEmpty) showNotice(context, str(r['action_note']));
    } on ApiException catch (e) {
      if (mounted) showNotice(context, e.message);
      if (e.conflict) await _loadAll();
    }
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    final t = _thread;
    if (t == null) {
      return Scaffold(
        appBar: AppBar(),
        body: FarmBackground(child: _error != null ? ErrorView(_error!, onRetry: _loadAll) : LoadingView('fos.market.loading'.tr())),
      );
    }
    final status = str(t['status']);
    final me = str(t['my_farmer_id']);
    final closed = _closed.contains(status);
    final handed = (t['handovers'] as List? ?? const []).map((e) => '$e').contains(me);
    final completed = (t['completions'] as List? ?? const []).map((e) => '$e').contains(me);
    final messages = _messages.keys.toList()..sort();
    final step = _trail.indexOf(status);
    return Scaffold(
      appBar: AppBar(
        title: Text(str(t['listing_title'], 'fos.market.exchange'.tr())),
        actions: [
          IconButton(
            tooltip: 'fos.market.review_with_mitra'.tr(),
            icon: const Icon(Icons.auto_awesome),
            onPressed: () => showExchangeMitra(context, intent: 'review_exchange', conversationId: widget.threadId),
          ),
        ],
      ),
      body: FarmBackground(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: FarmCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(kThreadStatus[status]?.tr() ?? statusLabel(status), style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: ink)),
                const SizedBox(height: 6),
                Row(children: [
                  for (var i = 0; i < _trail.length; i++)
                    Expanded(
                      child: Container(
                        height: 4,
                        margin: const EdgeInsets.symmetric(horizontal: 1),
                        color: i <= step ? AppColors.primary : (context.isDark ? Colors.white24 : Colors.black12),
                      ),
                    ),
                ]),
                if (asMap(t['proposal'])['terms'] != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text('fos.market.proposed_terms'.tr(namedArgs: {'text': '${asMap(t['proposal'])['terms']}'}), style: TextStyle(color: ink)),
                  ),
                if (!closed)
                  Wrap(spacing: 6, runSpacing: 4, children: [
                    if (status == 'open' || status == 'negotiating')
                      FilledButton.tonal(onPressed: () => _act('propose'), child: Text('fos.market.propose_terms'.tr())),
                    if (status == 'negotiating')
                      t['can_accept'] == true
                          ? FilledButton(onPressed: () => _act('accept'), child: Text('fos.market.agree'.tr()))
                          : Text('fos.market.waiting_other_farmer'.tr(), style: TextStyle(color: ink)),
                    if (status == 'agreed')
                      handed
                          ? Text('fos.market.handover_confirmed'.tr(), style: TextStyle(color: ink))
                          : FilledButton(onPressed: () => _act('handover'), child: Text('fos.market.confirm_handover'.tr())),
                    if (status == 'handover')
                      completed
                          ? Text('fos.market.waiting_other'.tr(), style: TextStyle(color: ink))
                          : FilledButton(onPressed: () => _act('complete'), child: Text('fos.market.confirm_complete'.tr())),
                    if (status == 'agreed' || status == 'handover')
                      TextButton(onPressed: () => _act('dispute'), child: Text('fos.market.problem'.tr())),
                    if (status == 'open' || status == 'negotiating')
                      TextButton(onPressed: () => _act('cancel'), child: Text('fos.market.close'.tr())),
                  ]),
              ]),
            ),
          ),
          Expanded(
            child: messages.isEmpty
                ? EmptyView(title: 'fos.market.no_messages'.tr())
                : ListView.builder(
                    reverse: true,
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    itemCount: messages.length,
                    itemBuilder: (_, i) {
                      final m = _messages[messages[messages.length - 1 - i]]!;
                      final mine = m['is_mine'] == true || str(m['sender_id']) == me;
                      return Align(
                        alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
                        child: Container(
                          margin: const EdgeInsets.symmetric(vertical: 3),
                          padding: const EdgeInsets.all(10),
                          constraints: BoxConstraints(maxWidth: MediaQuery.sizeOf(context).width * 0.78),
                          decoration: BoxDecoration(
                            color: mine ? AppColors.primary : (context.isDark ? AppColors.darkCard : Colors.white),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            if (!mine) Text(str(m['display_name'], 'fos.market.farmer'.tr()), style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: ink)),
                            Text(str(m['text']), style: TextStyle(color: mine ? Colors.white : ink)),
                            Text(displayDate(str(m['created_at']), withTime: true),
                                style: TextStyle(fontSize: 12, color: mine ? Colors.white70 : mutedColor(context))),
                          ]),
                        ),
                      );
                    },
                  ),
          ),
          if (!closed)
            SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Row(children: [
                  Expanded(
                    child: TextField(
                      controller: _text,
                      maxLength: 4000,
                      minLines: 1,
                      maxLines: 4,
                      decoration: InputDecoration(hintText: 'fos.market.message'.tr(), counterText: ''),
                    ),
                  ),
                  IconButton.filled(
                    tooltip: 'fos.market.send_message'.tr(),
                    onPressed: _sending
                        ? null
                        : () {
                            HapticFeedback.selectionClick();
                            _send();
                          },
                    icon: const Icon(Icons.send),
                  ),
                ]),
              ),
            ),
        ]),
      ),
    );
  }
}
