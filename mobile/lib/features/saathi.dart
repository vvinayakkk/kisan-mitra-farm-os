import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../assistant/widgets/farm_result.dart';
import '../core/api.dart';
import '../core/session.dart';
import '../core/workspace_cache.dart';
import '../ui/kit.dart';
import '../ui/loader.dart';
import '../utils/constants.dart';

/// Saathi's prepared suggestion for one area. It is a draft until the farmer
/// approves it; approval saves a plan in the notebook (no field work implied).
class PreparedBySaathi extends ConsumerStatefulWidget {
  const PreparedBySaathi({super.key, required this.area});

  /// today | markets | schemes | records | crops | exchange
  final String area;

  @override
  ConsumerState<PreparedBySaathi> createState() => _PreparedBySaathiState();
}

class _PreparedBySaathiState extends ConsumerState<PreparedBySaathi> {
  Map<String, dynamic>? _proposal;
  Map<String, dynamic>? _job;
  String? _error;
  bool _busy = false;
  bool _editing = false;
  bool _open = false;
  bool _autoPrepared = false;
  Timer? _poll;
  final _title = TextEditingController();
  final _steps = TextEditingController();

  ApiClient get _api => ref.read(apiProvider);
  bool get _working => const {'queued', 'running'}.contains(_job?['state']);

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _poll?.cancel();
    _title.dispose();
    _steps.dispose();
    super.dispose();
  }

  void _schedule(Duration after) {
    _poll?.cancel();
    _poll = Timer(after, _load);
  }

  Future<void> _load() async {
    try {
      final data = asMap(await _api.get('/api/companion/proposals', query: {'area': widget.area}));
      final proposals = asMaps(data['proposals']);
      if (!mounted) return;
      setState(() {
        _proposal = proposals.isEmpty ? null : proposals.first;
        _job = data['job'] == null ? null : asMap(data['job']);
        _error = null;
      });
      if (proposals.isEmpty && _job == null && !_autoPrepared) {
        _autoPrepared = true;
        await _prepare();
        return;
      }
      _schedule(_working ? const Duration(milliseconds: 2500) : const Duration(seconds: 60));
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = e.message);
      _schedule(const Duration(seconds: 15));
    }
  }

  Future<void> _prepare({bool research = false}) async {
    setState(() => _busy = true);
    try {
      await _api.post('/api/companion/prepare', body: {'area': widget.area, 'research': research});
      if (!mounted) return;
      setState(() => _job = {'state': 'queued'});
      _schedule(const Duration(milliseconds: 1500));
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _review(String action) async {
    final p = _proposal!;
    setState(() => _busy = true);
    try {
      final body = <String, Object?>{'action': action, 'row_version': p['row_version']};
      if (_editing && action != 'dismiss') {
        body['title'] = _title.text.trim();
        body['steps'] = _steps.text.split('\n').map((s) => s.trim()).where((s) => s.isNotEmpty).toList();
      }
      final result = asMap(await _api.post('/api/companion/proposals/${p['id']}/review', body: body));
      ref.read(workspaceCacheProvider).invalidate();
      final saved = asMap(result['proposal']);
      if (action == 'approve' && (saved['status'] != 'approved' || result['mission_id'] == null)) {
        throw ApiException(500, 'Your plan could not be confirmed. Try again.');
      }
      if (!mounted) return;
      setState(() {
        _editing = false;
        _proposal = action == 'dismiss' ? null : {...saved, 'mission_id': result['mission_id']};
      });
      if (action == 'approve') showNotice(context, 'Plan saved to your notebook.');
    } on ApiException catch (e) {
      if (mounted) {
        showNotice(context, e.message);
        if (e.conflict) unawaited(_load());
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = _proposal;
    final ink = inkColor(context);
    final approved = p?['status'] == 'approved';
    final steps = asMaps(p?['steps']);
    final evidence = asMaps(p?['evidence']);
    final research = asMap(p?['research']);
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: FarmCard(
        color: context.isDark ? AppColors.darkCard : const Color(0xFFF1F8E9),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Icon(Icons.spa_outlined, size: 16, color: AppColors.primaryDark),
            const SizedBox(width: 6),
            const Expanded(
              child: Text('PREPARED BY SAATHI',
                  style: TextStyle(
                      fontSize: 11, letterSpacing: 1, fontWeight: FontWeight.w700, color: AppColors.primaryDark)),
            ),
            if (approved)
              const Tag('Saved plan')
            else if (p != null)
              const Tag('Draft · not saved', color: AppColors.warning),
          ]),
          const SizedBox(height: 6),
          if (_working && p == null)
            Text('Reviewing your farm… You can keep using this page.', style: TextStyle(color: mutedColor(context)))
          else if (p == null)
            Text(
              _job?['state'] == 'failed'
                  ? 'Preparation was interrupted. Refresh to try again.'
                  : 'Prepare a useful next step from your farm records.',
              style: TextStyle(color: mutedColor(context)),
            )
          else if (_editing) ...[
            TextField(controller: _title, maxLength: 160, decoration: const InputDecoration(labelText: 'Plan title')),
            TextField(
              controller: _steps,
              minLines: 3,
              maxLines: 8,
              decoration: const InputDecoration(labelText: 'Steps (one per line, up to 12)'),
            ),
          ] else ...[
            Text(str(p['title'], 'A little help with your next step'),
                style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: ink)),
            if (str(p['summary']).isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(str(p['summary']),
                    maxLines: _open ? null : 2,
                    overflow: _open ? null : TextOverflow.ellipsis,
                    style: TextStyle(color: ink)),
              ),
            const SizedBox(height: 6),
            if (_open)
              for (final s in steps)
                Padding(
                  padding: const EdgeInsets.only(bottom: 3),
                  child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Icon(Icons.radio_button_unchecked, size: 14, color: mutedColor(context)),
                    const SizedBox(width: 6),
                    Expanded(child: Text(str(s['title']), style: TextStyle(color: ink))),
                  ]),
                ),
            if (_open && evidence.isNotEmpty)
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                shape: const Border(),
                title: Text('Based on your records · ${evidence.length}', style: const TextStyle(fontSize: 13)),
                children: [
                  for (final e in evidence)
                    ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      title: Text(str(e['label'])),
                      subtitle: str(e['detail']).isEmpty ? null : Text(str(e['detail'])),
                      trailing: str(e['url']).startsWith('http') ? const Icon(Icons.open_in_new, size: 16) : null,
                      onTap: str(e['url']).startsWith('http')
                          ? () => launchUrl(Uri.parse(str(e['url'])), mode: LaunchMode.externalApplication)
                          : null,
                    ),
                ],
              ),
            if (_open && research.isNotEmpty && research['status'] != 'not_requested') ResearchSources(research),
            if (asMap(research['preparation'])['translation_status'] == 'unavailable')
              Text('Translation is unavailable right now. This draft is in English.',
                  style: TextStyle(fontSize: 12, color: mutedColor(context))),
          ],
          if (_error != null) ErrorView(_error!, onRetry: _load),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 6, children: [
            // Approval is offered only after the farmer has opened the steps.
            if (p != null && !_open && !_editing)
              FilledButton.tonalIcon(
                onPressed: () => setState(() => _open = true),
                icon: const Icon(Icons.visibility_outlined, size: 18),
                label: Text('Review ${steps.length} steps'),
              ),
            if (p != null && _open && !approved && !_editing) ...[
              FilledButton.icon(
                onPressed: _busy ? null : () => _review('approve'),
                icon: const Icon(Icons.check, size: 18),
                label: Text('Approve & save plan · ${steps.length} steps'),
              ),
              OutlinedButton(
                onPressed: _busy
                    ? null
                    : () => setState(() {
                          _editing = true;
                          _title.text = str(p['title']);
                          _steps.text = steps.map((s) => str(s['title'])).join('\n');
                        }),
                child: const Text('Edit'),
              ),
              TextButton(onPressed: _busy ? null : () => _review('dismiss'), child: const Text('Dismiss')),
            ],
            if (_editing) ...[
              FilledButton(onPressed: _busy ? null : () => _review('edit'), child: const Text('Save draft changes')),
              TextButton(onPressed: () => setState(() => _editing = false), child: const Text('Cancel')),
            ],
            if (approved)
              OutlinedButton.icon(
                onPressed: () => context.push('/notebook?tab=missions'),
                icon: const Icon(Icons.menu_book_outlined, size: 18),
                label: const Text('View saved plan'),
              ),
            if (!_editing && (_open || p == null))
              TextButton.icon(
                onPressed: _busy || _working ? null : () => _prepare(),
                icon: const Icon(Icons.refresh, size: 18),
                label: Text(_working ? 'Preparing…' : 'Refresh'),
              ),
            if (!_editing && (_open || p == null) && (widget.area == 'markets' || widget.area == 'schemes'))
              TextButton.icon(
                onPressed: _busy || _working ? null : () => _prepare(research: true),
                icon: const Icon(Icons.travel_explore, size: 18),
                label: const Text('Research the web'),
              ),
          ]),
          if (p != null)
            Text(
              'Prepared ${displayDate(str(p['created_at'] ?? p['updated_at']))} · Approval saves a plan in your notebook.',
              style: TextStyle(fontSize: 11, color: mutedColor(context)),
            ),
        ]),
      ),
    );
  }
}

/// Saathi status, follow-up preferences, recent activity and WhatsApp link.
class SaathiScreen extends ConsumerStatefulWidget {
  const SaathiScreen({super.key});

  @override
  ConsumerState<SaathiScreen> createState() => _SaathiScreenState();
}

class _SaathiScreenState extends ConsumerState<SaathiScreen> {
  final _loader = GlobalKey<LoaderState<Map<String, dynamic>>>();

  static const _status = {
    'paused': 'Follow-ups paused',
    'quiet_hours': 'Quiet hours',
    'watching': 'Keeping an eye on your farm',
    'waiting_for_worker': 'Waiting to reconnect',
  };
  static const _frequencies = {
    1: 'Every hour',
    6: 'Every 6 hours',
    12: 'Twice a day',
    24: 'Once a day',
    168: 'Once a week'
  };

  Future<void> _savePrefs(Map<String, dynamic> settings, Map<String, Object?> patch) async {
    try {
      await ref.read(apiProvider).patch('/api/companion/preferences', body: {
        'row_version': settings['row_version'],
        'name': settings['name'],
        'enabled': settings['enabled'],
        'frequency_hours': settings['frequency_hours'],
        'quiet_start': settings['quiet_start'],
        'quiet_end': settings['quiet_end'],
        'timezone': settings['timezone'],
        ...patch,
      });
      if (mounted) showNotice(context, 'Saathi settings saved.');
    } on ApiException catch (e) {
      if (mounted) {
        showNotice(context, e.conflict ? 'Your companion settings changed. Refreshed — try again.' : e.message);
      }
    }
    _loader.currentState?.reload();
  }

  Future<void> _whatsapp(bool connected) async {
    final api = ref.read(apiProvider);
    try {
      if (connected) {
        await api.delete('/api/whatsapp/link');
      } else {
        final link = asMap(await api.post('/api/whatsapp/link'));
        if (!mounted) return;
        await showDialog<void>(
          context: context,
          builder: (c) => AlertDialog(
            title: const Text('Link WhatsApp'),
            content: SelectableText(
                'Send this one-time code from your WhatsApp within 10 minutes:\n\n${str(link['message'])}'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(c), child: const Text('Close')),
              if (str(link['url']).startsWith('https://'))
                FilledButton(
                  onPressed: () => launchUrl(Uri.parse(str(link['url'])), mode: LaunchMode.externalApplication),
                  child: const Text('Open WhatsApp'),
                ),
            ],
          ),
        );
      }
    } on ApiException catch (e) {
      if (mounted) showNotice(context, e.message);
    }
    _loader.currentState?.reload();
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    return Scaffold(
      appBar: AppBar(title: Text('Saathi', style: TextStyle(color: ink)), foregroundColor: ink),
      body: FarmBackground(
        child: Loader<Map<String, dynamic>>(
          key: _loader,
          loading: 'Connecting to Saathi…',
          load: () async => asMap(await ref.read(apiProvider).get('/api/companion')),
          builder: (context, data) {
            final settings = asMap(data['settings']);
            final activity = asMaps(data['activity']).take(6).toList();
            final whatsapp = asMap(asMap(data['channels'])['whatsapp']);
            final enabled = settings['enabled'] == true;
            return RefreshIndicator(
              onRefresh: () async => _loader.currentState?.reload(),
              child: ListView(padding: const EdgeInsets.all(16), children: [
                FarmCard(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(str(data['name'], 'Saathi'),
                        style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: ink)),
                    Text(_status[data['status']] ?? 'Connecting…', style: TextStyle(color: mutedColor(context))),
                    const SizedBox(height: 4),
                    Text(
                        'Saathi prepares reviewable suggestions in the background. It does not watch the weather '
                        'live, send messages or change records without your approval.',
                        style: TextStyle(fontSize: 12, color: mutedColor(context))),
                    SwitchListTile(
                      contentPadding: EdgeInsets.zero,
                      title: const Text('Background follow-ups'),
                      value: enabled,
                      onChanged: (v) => _savePrefs(settings, {'enabled': v}),
                    ),
                    DropdownButtonFormField<int>(
                      initialValue: _frequencies.containsKey(settings['frequency_hours'])
                          ? settings['frequency_hours'] as int
                          : null,
                      decoration: const InputDecoration(labelText: 'How often'),
                      items: [
                        for (final e in _frequencies.entries) DropdownMenuItem(value: e.key, child: Text(e.value))
                      ],
                      onChanged: (v) => v == null ? null : _savePrefs(settings, {'frequency_hours': v}),
                    ),
                    const SizedBox(height: 8),
                    Text(
                        'Quiet hours ${settings['quiet_start']}:00 – ${settings['quiet_end']}:00 (${str(settings['timezone'])})',
                        style: TextStyle(fontSize: 12, color: mutedColor(context))),
                  ]),
                ),
                const SectionTitle('Prepared for you'),
                const PreparedBySaathi(area: 'today'),
                const SectionTitle('Recent activity'),
                if (activity.isEmpty)
                  const EmptyView(title: 'Your next check-in will appear here.')
                else
                  for (final a in activity)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: FarmCard(
                        onTap: str(a['href']).contains('view=records')
                            ? () => context.push('/notebook?tab=missions')
                            : null,
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(str(a['title'], 'Farm check-in'),
                              style: TextStyle(fontWeight: FontWeight.w600, color: ink)),
                          Text(str(a['detail'], 'Review your farm notebook for the latest follow-ups.'),
                              style: TextStyle(color: mutedColor(context))),
                          Text(displayDate(str(a['created_at']), withTime: true),
                              style: TextStyle(fontSize: 11, color: mutedColor(context))),
                        ]),
                      ),
                    ),
                const SectionTitle('WhatsApp'),
                FarmCard(
                  child: whatsapp['configured'] != true
                      ? Text('WhatsApp connection is not configured on this server.',
                          style: TextStyle(color: mutedColor(context)))
                      : Row(children: [
                          Expanded(
                            child: Text(
                                whatsapp['connected'] == true ? str(whatsapp['masked_number'], 'Linked') : 'Not linked',
                                style: TextStyle(color: ink)),
                          ),
                          OutlinedButton(
                            onPressed: () => _whatsapp(whatsapp['connected'] == true),
                            child: Text(whatsapp['connected'] == true ? 'Unlink' : 'Link WhatsApp'),
                          ),
                        ]),
                ),
              ]),
            );
          },
        ),
      ),
    );
  }
}
