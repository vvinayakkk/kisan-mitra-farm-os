import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/api.dart';
import '../../core/ids.dart';
import '../../core/session.dart';
import '../../ui/kit.dart';
import '../../ui/loader.dart';
import '../../utils/constants.dart';
import 'exchange_mitra.dart';
import 'exchange_screen.dart';

const _closed = {'completed', 'cancelled', 'disputed'};
const _trail = ['open', 'negotiating', 'agreed', 'handover', 'completed'];
const _actionText = {
  'propose': 'Share these terms with the other farmer.',
  'accept': 'Agree to the terms. No payment happens in the app.',
  'handover': 'Confirm the handover on your side.',
  'complete': 'Confirm completion on your side.',
  'dispute': 'Describe the problem.',
  'cancel': 'Close this conversation.',
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
            title: const Text('Confirm step'),
            content: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(_actionText[action]!),
              if (action == 'accept' && asMap(t['proposal'])['terms'] != null) ...[
                const SizedBox(height: 8),
                Text('Terms: ${asMap(t['proposal'])['terms']}', style: const TextStyle(fontWeight: FontWeight.w600)),
              ],
              if (needsTerms)
                TextField(
                  controller: terms,
                  maxLines: 4,
                  maxLength: 4000,
                  onChanged: (_) => set(() {}),
                  decoration: InputDecoration(labelText: action == 'propose' ? 'Terms' : 'What went wrong'),
                ),
              if (action == 'propose')
                TextButton.icon(
                  onPressed: () => showExchangeMitra(c,
                      intent: 'draft_terms',
                      conversationId: widget.threadId,
                      onDraft: (d) => set(() => terms.text = str(d['text'], terms.text))),
                  icon: const Icon(Icons.auto_awesome, size: 16),
                  label: const Text('Draft with Mitra'),
                ),
            ]),
            actions: [
              TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('Back')),
              FilledButton(
                onPressed: needsTerms && terms.text.trim().length < 2 ? null : () => Navigator.pop(c, true),
                child: const Text('Confirm'),
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
        body: FarmBackground(child: _error != null ? ErrorView(_error!, onRetry: _loadAll) : const LoadingView('Loading…')),
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
        title: Text(str(t['listing_title'], 'Exchange')),
        actions: [
          IconButton(
            tooltip: 'Review with Mitra',
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
                Text(kThreadStatus[status] ?? status, style: TextStyle(fontWeight: FontWeight.w700, color: ink)),
                const SizedBox(height: 6),
                Row(children: [
                  for (var i = 0; i < _trail.length; i++)
                    Expanded(
                      child: Container(
                        height: 4,
                        margin: const EdgeInsets.symmetric(horizontal: 1),
                        color: i <= step ? AppColors.primary : Colors.black12,
                      ),
                    ),
                ]),
                if (asMap(t['proposal'])['terms'] != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text('Proposed terms: ${asMap(t['proposal'])['terms']}', style: TextStyle(color: ink)),
                  ),
                if (!closed)
                  Wrap(spacing: 6, runSpacing: 4, children: [
                    if (status == 'open' || status == 'negotiating')
                      FilledButton.tonal(onPressed: () => _act('propose'), child: const Text('Propose terms')),
                    if (status == 'negotiating')
                      t['can_accept'] == true
                          ? FilledButton(onPressed: () => _act('accept'), child: const Text('Agree'))
                          : const Text('Waiting for the other farmer.'),
                    if (status == 'agreed')
                      handed
                          ? const Text('Handover confirmed')
                          : FilledButton(onPressed: () => _act('handover'), child: const Text('Confirm handover')),
                    if (status == 'handover')
                      completed
                          ? const Text('Waiting for other farmer')
                          : FilledButton(onPressed: () => _act('complete'), child: const Text('Confirm complete')),
                    if (status == 'agreed' || status == 'handover')
                      TextButton(onPressed: () => _act('dispute'), child: const Text('Problem')),
                    if (status == 'open' || status == 'negotiating')
                      TextButton(onPressed: () => _act('cancel'), child: const Text('Close')),
                  ]),
              ]),
            ),
          ),
          Expanded(
            child: messages.isEmpty
                ? const EmptyView(title: 'No messages yet.')
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
                            if (!mine) Text(str(m['display_name'], 'Farmer'), style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
                            Text(str(m['text']), style: TextStyle(color: mine ? Colors.white : ink)),
                            Text(displayDate(str(m['created_at']), withTime: true),
                                style: TextStyle(fontSize: 10, color: mine ? Colors.white70 : mutedColor(context))),
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
                      decoration: const InputDecoration(hintText: 'Message', counterText: ''),
                    ),
                  ),
                  IconButton.filled(
                    tooltip: 'Send message',
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
