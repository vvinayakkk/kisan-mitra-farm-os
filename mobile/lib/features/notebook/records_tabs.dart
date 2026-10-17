import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../assistant/assistant_controller.dart';
import '../../core/api.dart';
import '../../core/session.dart';
import '../../core/workspace_cache.dart';
import '../../ui/form_sheet.dart';
import '../../ui/kit.dart';
import '../../ui/loader.dart';
import '../../ui/provenance.dart';
import '../../utils/constants.dart';
import 'shared_work.dart';

/// Runs a write, reports conflicts in plain words, and refreshes the list.
Future<bool> notebookWrite(BuildContext context, WidgetRef ref, Future<void> Function(ApiClient api) write,
    {String? done, GlobalKey<LoaderState>? reload}) async {
  try {
    await write(ref.read(apiProvider));
    ref.read(workspaceCacheProvider).invalidate();
    if (done != null && context.mounted) showNotice(context, done);
    return true;
  } on ApiException catch (e) {
    if (context.mounted) showNotice(context, e.conflict ? 'fos.notebook.changed_elsewhere'.tr() : e.message);
    return false;
  } finally {
    reload?.currentState?.reload();
  }
}

String rupees(Object? v) =>
    v is num ? '${v < 0 ? '−' : ''}₹${v.abs().toStringAsFixed(v % 1 == 0 ? 0 : 2)}' : '—';

class LedgerTab extends ConsumerStatefulWidget {
  const LedgerTab({super.key});

  @override
  ConsumerState<LedgerTab> createState() => _LedgerTabState();
}

class _LedgerTabState extends ConsumerState<LedgerTab> {
  final _loader = GlobalKey<LoaderState<Map<String, dynamic>>>();
  int _shown = 10;

  List<FieldSpec> _fields([Map<String, dynamic>? e]) => [
        FieldSpec('description', 'fos.notebook.what_for'.tr(), required: true, initial: e?['description'], maxLength: 200),
        FieldSpec('kind', 'fos.notebook.money'.tr(), kind: FieldKind.select, required: true, initial: e?['kind'] ?? 'expense',
            options: {'expense': 'fos.notebook.money_out'.tr(), 'income': 'fos.notebook.money_in'.tr()}),
        FieldSpec('basis', 'fos.notebook.status'.tr(), kind: FieldKind.select, required: true, initial: e?['basis'] ?? 'actual',
            options: {'actual': 'fos.notebook.actual'.tr(), 'estimated': 'fos.notebook.estimate'.tr(), 'receivable': 'fos.notebook.payment_due'.tr()}),
        FieldSpec('amount_inr', 'fos.notebook.amount_inr'.tr(), kind: FieldKind.number, required: true, initial: e?['amount_inr']),
        FieldSpec('occurred_on', 'fos.notebook.date'.tr(), kind: FieldKind.date, required: true, initial: e?['occurred_on'] ?? isoDate(DateTime.now())),
        FieldSpec('category', 'fos.notebook.category'.tr(), initial: e?['category'] ?? 'other', maxLength: 60),
        FieldSpec('notes', 'fos.notebook.notes'.tr(), kind: FieldKind.multiline, initial: e?['notes'], maxLength: 2000),
      ];

  Future<void> _edit([Map<String, dynamic>? entry]) async {
    final v = await showFormSheet(context,
        title: entry == null ? 'fos.notebook.add_entry'.tr() : 'fos.notebook.edit_entry'.tr(),
        fields: _fields(entry));
    if (v == null || !mounted) return;
    final body = {...v, 'category': v['category'] ?? 'other', 'notes': v['notes'] ?? '', 'cycle_id': entry?['cycle_id']};
    await notebookWrite(context, ref, (api) async {
      if (entry == null) {
        await api.post('/api/farm-workspace/ledger', body: body);
      } else {
        await api.patch('/api/farm-workspace/ledger/${entry['id']}', body: {...body, 'row_version': entry['row_version']});
      }
    }, done: 'fos.notebook.saved'.tr(), reload: _loader);
  }

  Future<void> _delete(Map<String, dynamic> e) async {
    if (!await confirmAction(context, title: 'fos.notebook.delete_entry_q'.tr(), body: str(e['description']), confirm: 'fos.notebook.delete'.tr())) return;
    if (!mounted) return;
    await notebookWrite(context, ref, (api) => api.delete('/api/farm-workspace/ledger/${e['id']}?row_version=${e['row_version']}'),
        done: 'fos.notebook.entry_removed'.tr(), reload: _loader);
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    return Loader<Map<String, dynamic>>(
      key: _loader,
      loading: 'fos.notebook.loading'.tr(),
      load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/ledger')),
      builder: (context, d) {
        final items = asMaps(d['items']);
        final s = asMap(d['summary']);
        return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
          FarmCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text('fos.notebook.balance'.tr(), style: TextStyle(fontWeight: FontWeight.w700, color: ink))),
                if (s['includes_demo_fixtures'] == true) Tag('fos.notebook.sample'.tr(), color: AppColors.warning),
              ]),
              const SizedBox(height: 6),
              Wrap(spacing: 18, runSpacing: 6, children: [
                _figure(context, 'fos.notebook.received'.tr(), s['actual_income']),
                _figure(context, 'fos.notebook.paid'.tr(), s['actual_expense']),
                _figure(context, 'fos.notebook.balance'.tr(), s['recorded_balance']),
              ]),
              const Divider(),
              Text('fos.notebook.estimates_dues'.tr(), style: TextStyle(fontSize: 12, color: mutedColor(context))),
              Wrap(spacing: 18, children: [
                _figure(context, 'fos.notebook.est_income'.tr(), s['estimated_income']),
                _figure(context, 'fos.notebook.est_costs'.tr(), s['estimated_expense']),
                _figure(context, 'fos.notebook.due_to_you'.tr(), s['receivable']),
              ]),
            ]),
          ),
          SectionTitle('fos.notebook.entries'.tr(), trailing: FilledButton.tonalIcon(onPressed: _edit, icon: const Icon(Icons.add), label: Text('fos.notebook.add'.tr()))),
          if (items.isEmpty) EmptyView(title: 'fos.notebook.no_entries'.tr()),
          for (final e in items.take(_shown))
            Card(
              child: ListTile(
                title: Row(children: [
                  Flexible(child: Text(str(e['description']), overflow: TextOverflow.ellipsis)),
                  const SizedBox(width: 6),
                  ProvenanceBadge({'origin': e['origin'] ?? 'user_reported'}),
                ]),
                subtitle: Text('${displayDate(str(e['occurred_on']))} · ${str(e['category'])} · '
                    '${e['basis'] == 'actual' ? (e['kind'] == 'income' ? 'fos.notebook.received'.tr() : 'fos.notebook.paid'.tr()) : e['basis'] == 'receivable' ? 'fos.notebook.payment_due'.tr() : 'fos.notebook.estimate'.tr()}'),
                trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                  Text('${e['kind'] == 'income' ? '+' : '−'}${rupees(e['amount_inr'])}',
                      style: TextStyle(fontWeight: FontWeight.w700, color: e['kind'] == 'income' ? accentColor(context) : ink)),
                  PopupMenuButton<String>(
                    onSelected: (v) => v == 'edit' ? _edit(e) : _delete(e),
                    itemBuilder: (_) => [
                      PopupMenuItem(value: 'edit', child: Text('fos.notebook.edit'.tr())),
                      PopupMenuItem(value: 'delete', child: Text('fos.notebook.delete'.tr())),
                    ],
                  ),
                ]),
              ),
            ),
          if (items.length > _shown)
            TextButton(onPressed: () => setState(() => _shown += 10), child: Text('fos.notebook.more'.tr())),
        ]);
      },
    );
  }

  Widget _figure(BuildContext context, String label, Object? v) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(rupees(v), style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: inkColor(context))),
        Text(label, style: TextStyle(fontSize: 11.5, color: mutedColor(context))),
      ]);
}

class CasesTab extends ConsumerStatefulWidget {
  const CasesTab({super.key});

  @override
  ConsumerState<CasesTab> createState() => _CasesTabState();
}

class _CasesTabState extends ConsumerState<CasesTab> {
  final _loader = GlobalKey<LoaderState<Map<String, dynamic>>>();
  Map<String, String> get _statuses => {'open': 'fos.notebook.open'.tr(), 'monitoring': 'fos.notebook.monitoring'.tr(), 'expert_review': 'fos.notebook.expert_review'.tr(), 'resolved': 'fos.notebook.resolved'.tr()};

  Future<void> _create() async {
    final v = await showFormSheet(context, title: 'fos.notebook.new_followup'.tr(), fields: [
      FieldSpec('title', 'fos.notebook.title'.tr(), required: true, maxLength: 160),
      FieldSpec('note', 'fos.notebook.first_observation'.tr(), kind: FieldKind.multiline, maxLength: 4000),
    ]);
    if (v == null || !mounted) return;
    await notebookWrite(context, ref, (api) => api.post('/api/farm-workspace/cases', body: {'title': v['title'], 'note': v['note'] ?? '', 'cycle_id': null}),
        done: 'fos.notebook.saved'.tr(), reload: _loader);
  }

  Future<void> _status(Map<String, dynamic> c, String status) => notebookWrite(context, ref,
      (api) => api.patch('/api/farm-workspace/cases/${c['id']}', body: {'title': c['title'], 'status': status, 'row_version': c['row_version']}),
      done: 'fos.notebook.status_saved'.tr(), reload: _loader);

  Future<void> _note(Map<String, dynamic> c) async {
    final v = await showFormSheet(context, title: 'fos.notebook.add_observation'.tr(), fields: [
      FieldSpec('note', 'fos.notebook.what_did_you_see'.tr(), kind: FieldKind.multiline, required: true, maxLength: 4000),
      FieldSpec('observed_on', 'fos.notebook.observed_on'.tr(), kind: FieldKind.date, required: true, initial: isoDate(DateTime.now())),
    ]);
    if (v == null || !mounted) return;
    await notebookWrite(context, ref, (api) => api.post('/api/farm-workspace/cases/${c['id']}/notes', body: v),
        done: 'fos.notebook.observation_saved'.tr(), reload: _loader);
  }

  @override
  Widget build(BuildContext context) => Loader<Map<String, dynamic>>(
        key: _loader,
        loading: 'fos.notebook.loading'.tr(),
        load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/cases')),
        builder: (context, d) {
          final items = asMaps(d['items']);
          return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
            SectionTitle('fos.notebook.followups'.tr(),
                trailing: FilledButton.tonalIcon(onPressed: _create, icon: const Icon(Icons.add), label: Text('fos.notebook.btn_new'.tr()))),
            if (items.isEmpty) EmptyView(title: 'fos.notebook.no_followups'.tr()),
            for (final c in items)
              Card(
                child: ExpansionTile(
                  shape: const Border(),
                  title: Text(str(c['title'])),
                  subtitle: Text('${_statuses[c['status']] ?? str(c['status']).replaceAll('_', ' ')} · '
                      '${'fos.notebook.notes_count'.tr(namedArgs: {'count': '${c['note_count'] ?? 0}'})} · ${displayDate(str(c['updated_at']))}'),
                  childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                  expandedCrossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (asMap(c['assessment']).isNotEmpty)
                      Text('fos.notebook.photo_assessment'.tr(namedArgs: {'text': str(asMap(c['assessment'])['description'])}),
                          maxLines: 4, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12.5, color: mutedColor(context))),
                    _CaseNotes(caseId: str(c['id'])),
                    Wrap(spacing: 8, children: [
                      FilledButton.tonal(onPressed: () => _note(c), child: Text('fos.notebook.add_observation'.tr())),
                      PopupMenuButton<String>(
                        onSelected: (s) => _status(c, s),
                        itemBuilder: (_) => [for (final e in _statuses.entries) PopupMenuItem(value: e.key, child: Text(e.value))],
                        child: Chip(label: Text('fos.notebook.change_status'.tr())),
                      ),
                    ]),
                  ],
                ),
              ),
          ]);
        },
      );
}

class _CaseNotes extends ConsumerWidget {
  const _CaseNotes({required this.caseId});

  final String caseId;

  @override
  Widget build(BuildContext context, WidgetRef ref) => Loader<Map<String, dynamic>>(
        loading: 'fos.notebook.loading'.tr(),
        load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/cases/$caseId/notes')),
        builder: (context, d) {
          final notes = asMaps(d['items']);
          if (notes.isEmpty) return Padding(padding: const EdgeInsets.all(8), child: Text('fos.notebook.nothing_yet'.tr()));
          return Column(children: [
            for (final n in notes)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text(str(n['note'])),
                subtitle: Text('fos.notebook.observed_date'.tr(namedArgs: {'date': displayDate(str(n['observed_on']))})),
              ),
          ]);
        },
      );
}

class MissionsTab extends ConsumerStatefulWidget {
  const MissionsTab({super.key});

  @override
  ConsumerState<MissionsTab> createState() => _MissionsTabState();
}

class _MissionsTabState extends ConsumerState<MissionsTab> {
  final _loader = GlobalKey<LoaderState<Map<String, dynamic>>>();

  static const _transitions = {
    'draft': ['active', 'cancelled'],
    'active': ['paused', 'completed', 'cancelled'],
    'paused': ['active', 'cancelled'],
  };
  Map<String, String> get _labels => {'active': 'fos.notebook.start'.tr(), 'paused': 'fos.notebook.pause'.tr(), 'completed': 'fos.notebook.complete'.tr(), 'cancelled': 'fos.notebook.cancel'.tr()};

  String _statusName(String s) => switch (s) {
        'draft' => 'fos.notebook.st_draft'.tr(),
        'active' => 'fos.notebook.st_active'.tr(),
        'paused' => 'fos.notebook.st_paused'.tr(),
        'completed' => 'fos.notebook.st_completed'.tr(),
        'cancelled' => 'fos.notebook.st_cancelled'.tr(),
        _ => s,
      };

  Future<void> _save(Map<String, dynamic> m, {List<Map<String, dynamic>>? steps, String? status}) => notebookWrite(
        context,
        ref,
        (api) => api.patch('/api/farm-workspace/missions/${m['id']}', body: {
          'title': m['title'],
          'objective': m['objective'] ?? '',
          'steps': steps ?? asMaps(m['steps']),
          'status': status ?? m['status'],
          'row_version': m['row_version'],
        }),
        reload: _loader,
      );

  Future<void> _create() async {
    final v = await showFormSheet(context, title: 'fos.notebook.new_plan'.tr(), fields: [
      FieldSpec('title', 'fos.notebook.plan_title'.tr(), required: true, maxLength: 160),
      FieldSpec('objective', 'fos.notebook.goal'.tr(), kind: FieldKind.multiline, maxLength: 2000),
      FieldSpec('steps', 'fos.notebook.steps_hint'.tr(), kind: FieldKind.multiline),
    ]);
    if (v == null || !mounted) return;
    final steps = '${v['steps'] ?? ''}'.split('\n').map((s) => s.trim()).where((s) => s.isNotEmpty).take(30)
        .map((s) => {'title': s, 'done': false}).toList();
    await notebookWrite(context, ref,
        (api) => api.post('/api/farm-workspace/missions', body: {'title': v['title'], 'objective': v['objective'] ?? '', 'steps': steps}),
        done: 'fos.notebook.plan_saved_draft'.tr(), reload: _loader);
  }

  @override
  Widget build(BuildContext context) {
    final assistant = ref.watch(assistantProvider);
    return Loader<Map<String, dynamic>>(
      key: _loader,
      loading: 'fos.notebook.loading'.tr(),
      load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/missions')),
      builder: (context, d) {
        final items = asMaps(d['items']);
        return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
          SectionTitle('fos.notebook.plans'.tr(), trailing: FilledButton.tonalIcon(onPressed: _create, icon: const Icon(Icons.add), label: Text('fos.notebook.new_plan'.tr()))),
          if (items.isEmpty) EmptyView(title: 'fos.notebook.no_plans'.tr()),
          for (final m in items) _mission(context, m, assistant),
          const SharedFarmWork(),
        ]);
      },
    );
  }

  Widget _mission(BuildContext context, Map<String, dynamic> m, AssistantState assistant) {
    final steps = asMaps(m['steps']);
    final status = str(m['status']);
    final locked = status == 'completed' || status == 'cancelled';
    final done = steps.where((s) => s['done'] == true).length;
    return Card(
      child: ExpansionTile(
        shape: const Border(),
        initiallyExpanded: status == 'active',
        title: Text(str(m['title'])),
        subtitle: Text('fos.notebook.mission_progress'.tr(namedArgs: {'status': _statusName(status), 'done': '$done', 'total': '${steps.length}'})),
        childrenPadding: const EdgeInsets.fromLTRB(8, 0, 8, 12),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (str(m['objective']).isNotEmpty) Padding(padding: const EdgeInsets.all(8), child: Text(str(m['objective']))),
          for (var i = 0; i < steps.length; i++)
            CheckboxListTile(
              dense: true,
              value: steps[i]['done'] == true,
              onChanged: locked
                  ? null
                  : (v) {
                      HapticFeedback.selectionClick();
                      _save(m, steps: [
                        for (var j = 0; j < steps.length; j++) j == i ? {...steps[j], 'done': v ?? false} : steps[j],
                      ]);
                    },
              title: Text(str(steps[i]['title'])),
            ),
          Wrap(spacing: 8, runSpacing: 6, children: [
            for (final next in _transitions[status] ?? const <String>[])
              FilledButton.tonal(
                onPressed: next == 'completed' && done < steps.length
                    ? null
                    : () {
                        HapticFeedback.selectionClick();
                        _save(m, status: next);
                      },
                child: Text(_labels[next]!),
              ),
            if (status == 'active' || status == 'draft')
              FilledButton.tonal(
                onPressed: assistant.busy || assistant.pending != null
                    ? null
                    : () {
                        ref.read(assistantProvider.notifier).send(
                              'fos.notebook.ask_mitra_prompt'.tr(namedArgs: {'title': '${m['title']}'}),
                              context: RunContext(view: 'records', missionId: str(m['id'])),
                            );
                        context.push('/chat');
                      },
                child: Text('fos.notebook.ask_mitra'.tr()),
              ),
          ]),
          _Receipts(missionId: str(m['id'])),
        ],
      ),
    );
  }
}

class _Receipts extends ConsumerWidget {
  const _Receipts({required this.missionId});

  final String missionId;

  @override
  Widget build(BuildContext context, WidgetRef ref) => ExpansionTile(
        title: Text('fos.notebook.activity'.tr(), style: const TextStyle(fontSize: 13)),
        children: [
          Loader<Map<String, dynamic>>(
            loading: 'fos.notebook.loading'.tr(),
            load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/missions/$missionId/receipts')),
            builder: (context, d) {
              final items = asMaps(d['items']);
              if (items.isEmpty) return Padding(padding: const EdgeInsets.all(8), child: Text('fos.notebook.nothing_yet'.tr()));
              return Column(children: [
                for (final r in items)
                  ListTile(
                    dense: true,
                    title: Text(str(r['action']).replaceAll('_', ' ')),
                    subtitle: Text(displayDate(str(r['created_at']), withTime: true)),
                  ),
              ]);
            },
          ),
        ],
      );
}

class MemoryTab extends ConsumerStatefulWidget {
  const MemoryTab({super.key});

  @override
  ConsumerState<MemoryTab> createState() => _MemoryTabState();
}

class _MemoryTabState extends ConsumerState<MemoryTab> {
  final _loader = GlobalKey<LoaderState<Map<String, dynamic>>>();

  String _value(Object? v) {
    final m = asMap(v);
    return m['content'] != null ? str(m['content']) : m.isEmpty ? str(v) : m.entries.map((e) => '${e.key}: ${e.value}').join(', ');
  }

  @override
  Widget build(BuildContext context) => Loader<Map<String, dynamic>>(
        key: _loader,
        loading: 'fos.notebook.loading'.tr(),
        load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/memories')),
        builder: (context, d) {
          final items = asMaps(d['items']);
          return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
            SectionTitle('fos.notebook.saved_facts'.tr()),
            if (items.isEmpty) EmptyView(title: 'fos.notebook.no_facts'.tr()),
            for (final m in items)
              Card(
                child: ListTile(
                  title: Text(_value(m['value'])),
                  subtitle: Text('${str(m['fact_key']).replaceAll('.', ' · ')} · ${displayDate(str(m['valid_from']))}'),
                  trailing: PopupMenuButton<String>(
                    onSelected: (action) async {
                      if (action == 'forget') {
                        if (!await confirmAction(context,
                            title: 'fos.notebook.forget_q'.tr(),
                            body: 'fos.notebook.forget_body'.tr(),
                            confirm: 'fos.notebook.forget'.tr())) {
                          return;
                        }
                        if (!context.mounted) return;
                        await notebookWrite(context, ref, (api) => api.delete('/api/farm-workspace/memories/${m['id']}'),
                            done: 'fos.notebook.fact_forgotten'.tr(), reload: _loader);
                      } else {
                        final v = await showFormSheet(context, title: 'fos.notebook.correct_fact'.tr(), fields: [
                          FieldSpec('value', 'fos.notebook.value'.tr(), kind: FieldKind.multiline, required: true, initial: _value(m['value']), maxLength: 2000),
                        ]);
                        if (v == null || !context.mounted) return;
                        await notebookWrite(context, ref, (api) => api.patch('/api/farm-workspace/memories/${m['id']}', body: v),
                            done: 'fos.notebook.correction_saved'.tr(), reload: _loader);
                      }
                    },
                    itemBuilder: (_) => [
                      PopupMenuItem(value: 'correct', child: Text('fos.notebook.correct'.tr())),
                      PopupMenuItem(value: 'forget', child: Text('fos.notebook.forget'.tr())),
                    ],
                  ),
                ),
              ),
          ]);
        },
      );
}
