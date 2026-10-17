import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
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
      setState(() => _error = 'fos.market.catalog_unavailable'.tr().tr());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final schemes = _schemes;
    return Scaffold(
      appBar: AppBar(title: Text('fos.market.support_title'.tr())),
      floatingActionButton: const HelperButton(contextKey: 'schemes'),
      body: FarmBackground(
        child: ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 96), children: [
          const PreparedBySaathi(area: 'schemes'),
          FarmCard(
            child: Column(children: [
              TextField(controller: _query, decoration: InputDecoration(labelText: 'fos.market.search_support'.tr(), hintText: 'fos.market.search_hint'.tr())),
              const SizedBox(height: 8),
              TextField(controller: _state, decoration: InputDecoration(labelText: 'fos.market.state_optional'.tr())),
              const SizedBox(height: 8),
              Align(
                alignment: Alignment.centerRight,
                child: FilledButton.icon(onPressed: _busy ? null : _search, icon: const Icon(Icons.search), label: Text('fos.market.search'.tr())),
              ),
            ]),
          ),
          if (_busy) LoadingView('fos.market.loading'.tr()),
          if (_error != null) ErrorView(_error!, onRetry: _search),
          if (!_busy && schemes != null && schemes.isEmpty)
            EmptyView(title: 'fos.market.no_matches'.tr()),
          if (!_busy && schemes != null && schemes.isNotEmpty) ...[
            SectionTitle('fos.market.references'.tr(namedArgs: {'count': '${schemes.length}'})),
            for (final s in schemes.take(_shown)) _SchemeCard(scheme: s),
            if (schemes.length > _shown)
              TextButton(onPressed: () => setState(() => _shown += 6), child: Text('fos.market.more'.tr())),
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
    final title = str(scheme['scheme_name'], str(scheme['name'], str(scheme['title'], 'fos.market.programme'.tr())));
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
            str(scheme['state'], 'fos.market.national'.tr()),
            style: TextStyle(fontSize: 12, color: mutedColor(context)),
          ),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (description.isNotEmpty) Text(description, style: TextStyle(color: ink)),
            if (str(scheme['eligibility']).isNotEmpty) ...[
              const SizedBox(height: 6),
              Text('fos.market.who_can_apply'.tr(namedArgs: {'text': '${scheme['eligibility']}'}), style: TextStyle(color: ink)),
            ],
            const SizedBox(height: 8),
            if (_uuid.hasMatch(id)) _SupportChecklist(schemeId: id),
            Wrap(spacing: 8, children: [
              if (url.startsWith('https://') || url.startsWith('http://'))
                FilledButton.tonalIcon(
                  onPressed: () => launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication),
                  icon: const Icon(Icons.open_in_new, size: 16),
                  label: Text('fos.market.official_page'.tr()),
                ),
              FilledButton.tonalIcon(
                onPressed: () {
                  HapticFeedback.selectionClick();
                  ref.read(assistantProvider.notifier).send(
                        'fos.market.prepare_prompt'.tr(namedArgs: {'title': title}) +
                            (str(scheme['state']).isEmpty ? '' : 'fos.market.prepare_in_state'.tr(namedArgs: {'state': '${scheme['state']}'})) +
                            (url.isEmpty ? '' : 'fos.market.prepare_official'.tr(namedArgs: {'url': url})) +
                            'fos.market.prepare_verify'.tr(),
                        context: const RunContext(view: 'schemes'),
                      );
                  showHelperSheet(context, 'schemes');
                },
                icon: const Icon(Icons.eco, size: 16),
                label: Text('fos.market.prepare'.tr()),
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
    'eligibility_reviewed': 'fos.market.chk_eligibility',
    'documents_reviewed': 'fos.market.chk_documents',
    'application_reviewed': 'fos.market.chk_application',
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
    if (f == null) return LoadingView('fos.market.loading'.tr());
    final done = _items.keys.where((k) => f[k] == true).length;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(
          'fos.market.checklist'.tr(namedArgs: {
            'status': _saving
                ? 'fos.market.saving'.tr()
                : 'fos.market.checklist_done'.tr(namedArgs: {'done': '$done'}) + ((f['row_version'] ?? 0) > 0 ? ' · ${'fos.market.saved'.tr()}' : ''),
          }),
          style: TextStyle(fontWeight: FontWeight.w600, color: context.isDark ? AppColors.primaryLight : AppColors.primaryDark)),
      for (final e in _items.entries)
        CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          dense: true,
          value: f[e.key] == true,
          onChanged: _saving
              ? null
              : (v) {
                  HapticFeedback.selectionClick();
                  _toggle(e.key, v ?? false);
                },
          title: Text(e.value.tr(), style: TextStyle(color: inkColor(context))),
        ),
      Text('fos.market.checklist_note'.tr(), style: TextStyle(fontSize: 11, color: mutedColor(context))),
      const SizedBox(height: 6),
    ]);
  }
}
