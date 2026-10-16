import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../assistant/assistant_controller.dart';
import '../assistant/helper_sheet.dart';
import '../core/api.dart';
import '../core/session.dart';
import '../ui/kit.dart';
import '../ui/loader.dart';
import '../utils/constants.dart';
import 'saathi.dart';
import 'workspace_tools.dart';

final _uuid = RegExp(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$');

/// Programme references and the farmer's own preparation checklist. Nothing
/// here applies for a scheme or implies eligibility.
class SchemesScreen extends ConsumerStatefulWidget {
  const SchemesScreen({super.key});

  @override
  ConsumerState<SchemesScreen> createState() => _SchemesScreenState();
}

class _SchemesScreenState extends ConsumerState<SchemesScreen> {
  final _query = TextEditingController();
  final _state = TextEditingController();
  List<Map<String, dynamic>>? _schemes;
  String? _error;
  bool _busy = false;
  int _shown = 6;

  @override
  void initState() {
    super.initState();
    _search();
  }

  Future<void> _search() async {
    setState(() {
      _busy = true;
      _error = null;
      _shown = 6;
    });
    try {
      final data = await ref.read(workspaceToolsProvider).inspect('scheme_search', {'query': _query.text.trim(), 'state': _state.text.trim()});
      setState(() => _schemes = asMaps(data['schemes']));
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'The catalog is unavailable.');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    final schemes = _schemes;
    return Scaffold(
      appBar: AppBar(title: Text('Farm support', style: TextStyle(color: ink)), foregroundColor: ink),
      floatingActionButton: const HelperButton(contextKey: 'schemes'),
      body: FarmBackground(
        child: ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 96), children: [
          const PreparedBySaathi(area: 'schemes'),
          FarmCard(
            child: Column(children: [
              TextField(controller: _query, decoration: const InputDecoration(labelText: 'What support do you need?', hintText: 'e.g. irrigation, insurance')),
              const SizedBox(height: 8),
              TextField(controller: _state, decoration: const InputDecoration(labelText: 'State (optional)')),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton.icon(onPressed: _busy ? null : _search, icon: const Icon(Icons.search), label: const Text('Find support')),
              ),
            ]),
          ),
          if (_busy) const LoadingView('Finding relevant support…'),
          if (_error != null) ErrorView(_error!, onRetry: _search),
          if (!_busy && schemes != null && schemes.isEmpty)
            const EmptyView(title: 'Let’s try a broader search.', detail: 'No matching catalog entries. Try another keyword or leave the state blank.'),
          if (!_busy && schemes != null && schemes.isNotEmpty) ...[
            SectionTitle('${schemes.length} relevant references'),
            for (final s in schemes.take(_shown)) _SchemeCard(scheme: s),
            if (schemes.length > _shown)
              TextButton(onPressed: () => setState(() => _shown += 6), child: Text('More support · $_shown of ${schemes.length}')),
          ],
        ]),
      ),
    );
  }
}

class _SchemeCard extends ConsumerWidget {
  const _SchemeCard({required this.scheme});

  final Map<String, dynamic> scheme;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ink = inkColor(context);
    final id = str(scheme['scheme_id'], str(scheme['id']));
    final title = str(scheme['scheme_name'], str(scheme['name'], str(scheme['title'], 'Programme')));
    final url = str(scheme['official_url'], str(scheme['website']));
    final requirements = asMap(scheme['requirements']);
    final description = str(scheme['benefit_description'], str(scheme['description'], str(requirements['summary'])));
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: FarmCard(
        padding: EdgeInsets.zero,
        child: ExpansionTile(
          shape: const Border(),
          title: Text(title, style: TextStyle(fontWeight: FontWeight.w700, color: ink)),
          subtitle: Text(
            '${str(scheme['state'], 'National support')} · ${scheme['source'] == 'fallback' ? 'Reference catalog' : 'Programme details'}',
            style: TextStyle(fontSize: 12, color: mutedColor(context)),
          ),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (description.isNotEmpty) Text(description, style: TextStyle(color: ink)),
            if (str(scheme['eligibility']).isNotEmpty) ...[
              const SizedBox(height: 6),
              Text('Who can apply: ${scheme['eligibility']}', style: TextStyle(color: ink)),
            ],
            const SizedBox(height: 8),
            if (_uuid.hasMatch(id)) _SupportChecklist(schemeId: id),
            Wrap(spacing: 8, children: [
              if (url.startsWith('https://') || url.startsWith('http://'))
                OutlinedButton.icon(
                  onPressed: () => launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication),
                  icon: const Icon(Icons.open_in_new, size: 16),
                  label: const Text('Official page'),
                ),
              FilledButton.tonalIcon(
                onPressed: () {
                  ref.read(assistantProvider.notifier).send(
                        'Help me prepare for the scheme “$title”${str(scheme['state']).isEmpty ? '' : ' in ${scheme['state']}'}'
                        '${url.isEmpty ? '' : ' (official page: $url)'}. Verify the official requirements and ask what you need from me.',
                        context: const RunContext(view: 'schemes'),
                      );
                  showHelperSheet(context, 'schemes');
                },
                icon: const Icon(Icons.eco, size: 16),
                label: const Text('Prepare with Mitra'),
              ),
            ]),
          ],
        ),
      ),
    );
  }
}

class _SupportChecklist extends ConsumerStatefulWidget {
  const _SupportChecklist({required this.schemeId});

  final String schemeId;

  @override
  ConsumerState<_SupportChecklist> createState() => _SupportChecklistState();
}

class _SupportChecklistState extends ConsumerState<_SupportChecklist> {
  Map<String, dynamic>? _folder;
  String? _error;
  bool _saving = false;

  static const _items = {
    'eligibility_reviewed': 'I have checked who can apply',
    'documents_reviewed': 'I have checked the documents needed',
    'application_reviewed': 'I have checked the deadline and application route',
  };

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final data = asMap(await ref.read(apiProvider).get('/api/support-folder/${widget.schemeId}'));
      if (mounted) {
      setState(() {
        _folder = data;
        _error = null;
      });
    }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  Future<void> _toggle(String key, bool value) async {
    final before = _folder!;
    setState(() {
      _folder = {...before, key: value};
      _saving = true;
    });
    try {
      final saved = asMap(await ref.read(apiProvider).put('/api/support-folder/${widget.schemeId}', body: {
        'row_version': before['row_version'] ?? 0,
        for (final k in _items.keys) k: k == key ? value : before[k] == true,
      }));
      if (mounted) setState(() => _folder = saved.isEmpty ? _folder : saved);
      if (saved.isEmpty) await _load();
    } on ApiException catch (e) {
      if (mounted) {
      setState(() {
        _folder = before;
        _error = e.message;
      });
    }
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final f = _folder;
    if (_error != null) return ErrorView(_error!, onRetry: _load);
    if (f == null) return const LoadingView('Loading your checklist…');
    final done = _items.keys.where((k) => f[k] == true).length;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Your preparation · ${_saving ? 'Syncing…' : '$done of 3 checked${(f['row_version'] ?? 0) > 0 ? ' · Saved' : ''}'}',
          style: const TextStyle(fontWeight: FontWeight.w600, color: AppColors.primaryDark)),
      for (final e in _items.entries)
        CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          dense: true,
          value: f[e.key] == true,
          onChanged: _saving ? null : (v) => _toggle(e.key, v ?? false),
          title: Text(e.value),
        ),
      Text('Your own checklist. It does not submit an application or confirm eligibility.',
          style: TextStyle(fontSize: 11, color: mutedColor(context))),
      const SizedBox(height: 6),
    ]);
  }
}
