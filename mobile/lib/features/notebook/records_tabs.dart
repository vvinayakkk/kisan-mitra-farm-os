import 'package:flutter/material.dart';
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
    if (context.mounted) showNotice(context, e.conflict ? 'This record changed elsewhere. Showing the latest version.' : e.message);
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
        FieldSpec('description', 'What was it for', required: true, initial: e?['description'], maxLength: 200),
        FieldSpec('kind', 'Money', kind: FieldKind.select, required: true, initial: e?['kind'] ?? 'expense',
            options: const {'expense': 'Money out (cost)', 'income': 'Money in'}),
        FieldSpec('basis', 'Status', kind: FieldKind.select, required: true, initial: e?['basis'] ?? 'actual',
            options: const {'actual': 'Actual payment / receipt', 'estimated': 'Estimate', 'receivable': 'Payment due (income only)'}),
        FieldSpec('amount_inr', 'Amount (₹)', kind: FieldKind.number, required: true, initial: e?['amount_inr']),
        FieldSpec('occurred_on', 'Date', kind: FieldKind.date, required: true, initial: e?['occurred_on'] ?? isoDate(DateTime.now())),
        FieldSpec('category', 'Category', initial: e?['category'] ?? 'other', maxLength: 60),
        FieldSpec('notes', 'Notes', kind: FieldKind.multiline, initial: e?['notes'], maxLength: 2000),
      ];

  Future<void> _edit([Map<String, dynamic>? entry]) async {
    final v = await showFormSheet(context,
        title: entry == null ? 'Add entry' : 'Edit entry',
        fields: _fields(entry),
        note: 'Actual entries cannot be future-dated. Estimates stay separate from paid amounts.');
    if (v == null || !mounted) return;
    final body = {...v, 'category': v['category'] ?? 'other', 'notes': v['notes'] ?? '', 'cycle_id': entry?['cycle_id']};
    await notebookWrite(context, ref, (api) async {
      if (entry == null) {
        await api.post('/api/farm-workspace/ledger', body: body);
      } else {
        await api.patch('/api/farm-workspace/ledger/${entry['id']}', body: {...body, 'row_version': entry['row_version']});
      }
    }, done: 'Saved to your ledger.', reload: _loader);
  }

  Future<void> _delete(Map<String, dynamic> e) async {
    if (!await confirmAction(context, title: 'Delete this entry?', body: str(e['description']), confirm: 'Confirm delete')) return;
    if (!mounted) return;
    await notebookWrite(context, ref, (api) => api.delete('/api/farm-workspace/ledger/${e['id']}?row_version=${e['row_version']}'),
        done: 'Entry removed.', reload: _loader);
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    return Loader<Map<String, dynamic>>(
      key: _loader,
      loading: 'Loading saved records…',
      load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/ledger')),
      builder: (context, d) {
        final items = asMaps(d['items']);
        final s = asMap(d['summary']);
        return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
          FarmCard(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text('Money in & money out', style: TextStyle(fontWeight: FontWeight.w700, color: ink))),
                if (s['includes_demo_fixtures'] == true) const Tag('Sample', color: AppColors.warning),
              ]),
              const SizedBox(height: 6),
              Wrap(spacing: 18, runSpacing: 6, children: [
                _figure(context, 'Money received', s['actual_income']),
                _figure(context, 'Costs paid', s['actual_expense']),
                _figure(context, 'Recorded balance', s['recorded_balance']),
              ]),
              const Divider(),
              Text('Estimates and payments due', style: TextStyle(fontSize: 12, color: mutedColor(context))),
              Wrap(spacing: 18, children: [
                _figure(context, 'Estimated income', s['estimated_income']),
                _figure(context, 'Estimated costs', s['estimated_expense']),
                _figure(context, 'Payments due to you', s['receivable']),
              ]),
              if (str(s['note']).isNotEmpty)
                Text(str(s['note']), style: TextStyle(fontSize: 11.5, color: mutedColor(context))),
            ]),
          ),
          SectionTitle('Entries', trailing: FilledButton.tonalIcon(onPressed: _edit, icon: const Icon(Icons.add), label: const Text('Add entry'))),
          if (items.isEmpty) const EmptyView(title: 'Nothing saved here yet.', detail: 'Add your first record when you’re ready.'),
          for (final e in items.take(_shown))
            Card(
              child: ListTile(
                title: Row(children: [
                  Flexible(child: Text(str(e['description']), overflow: TextOverflow.ellipsis)),
                  const SizedBox(width: 6),
                  ProvenanceBadge({'origin': e['origin'] ?? 'user_reported'}),
                ]),
                subtitle: Text('${displayDate(str(e['occurred_on']))} · ${str(e['category'])} · '
                    '${e['basis'] == 'actual' ? (e['kind'] == 'income' ? 'Received' : 'Paid') : e['basis'] == 'receivable' ? 'Payment due' : 'Estimate'}'),
                trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                  Text('${e['kind'] == 'income' ? '+' : '−'}${rupees(e['amount_inr'])}',
                      style: TextStyle(fontWeight: FontWeight.w700, color: e['kind'] == 'income' ? AppColors.primaryDark : ink)),
                  PopupMenuButton<String>(
                    onSelected: (v) => v == 'edit' ? _edit(e) : _delete(e),
                    itemBuilder: (_) => const [
                      PopupMenuItem(value: 'edit', child: Text('Edit')),
                      PopupMenuItem(value: 'delete', child: Text('Delete')),
                    ],
                  ),
                ]),
              ),
            ),
          if (items.length > _shown)
            TextButton(onPressed: () => setState(() => _shown += 10), child: Text('Show more records (${items.length - _shown})')),
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
  static const _statuses = {'open': 'Open', 'monitoring': 'Monitoring', 'expert_review': 'Expert review', 'resolved': 'Resolved'};

  Future<void> _create() async {
    final v = await showFormSheet(context, title: 'New crop follow-up', fields: const [
      FieldSpec('title', 'What are you following', required: true, maxLength: 160),
      FieldSpec('note', 'First observation', kind: FieldKind.multiline, maxLength: 4000),
    ]);
    if (v == null || !mounted) return;
    await notebookWrite(context, ref, (api) => api.post('/api/farm-workspace/cases', body: {'title': v['title'], 'note': v['note'] ?? '', 'cycle_id': null}),
        done: 'Follow-up opened.', reload: _loader);
  }

  Future<void> _status(Map<String, dynamic> c, String status) => notebookWrite(context, ref,
      (api) => api.patch('/api/farm-workspace/cases/${c['id']}', body: {'title': c['title'], 'status': status, 'row_version': c['row_version']}),
      done: 'Status saved.', reload: _loader);

  Future<void> _note(Map<String, dynamic> c) async {
    final v = await showFormSheet(context, title: 'Add a dated observation', fields: [
      const FieldSpec('note', 'What did you see', kind: FieldKind.multiline, required: true, maxLength: 4000),
      FieldSpec('observed_on', 'Observed on', kind: FieldKind.date, required: true, initial: isoDate(DateTime.now())),
    ], note: 'Observation dates cannot be in the future.');
    if (v == null || !mounted) return;
    await notebookWrite(context, ref, (api) => api.post('/api/farm-workspace/cases/${c['id']}/notes', body: v),
        done: 'Observation saved.', reload: _loader);
  }

  @override
  Widget build(BuildContext context) => Loader<Map<String, dynamic>>(
        key: _loader,
        loading: 'Loading saved records…',
        load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/cases')),
        builder: (context, d) {
          final items = asMaps(d['items']);
          return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
            SectionTitle('Crop follow-ups',
                trailing: FilledButton.tonalIcon(onPressed: _create, icon: const Icon(Icons.add), label: const Text('New follow-up'))),
            if (str(d['note']).isNotEmpty) Text(str(d['note']), style: TextStyle(fontSize: 12, color: mutedColor(context))),
            if (items.isEmpty) const EmptyView(title: 'Nothing saved here yet.', detail: 'Open a follow-up to keep a dated symptom timeline.'),
            for (final c in items)
              Card(
                child: ExpansionTile(
                  shape: const Border(),
                  title: Text(str(c['title'])),
                  subtitle: Text('${_statuses[c['status']] ?? str(c['status']).replaceAll('_', ' ')} · '
                      '${c['note_count'] ?? 0} observations · updated ${displayDate(str(c['updated_at']))}'),
                  childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                  expandedCrossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (asMap(c['assessment']).isNotEmpty)
                      Text('Photo assessment: ${str(asMap(c['assessment'])['description'])}',
                          maxLines: 4, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12.5, color: mutedColor(context))),
                    _CaseNotes(caseId: str(c['id'])),
                    Wrap(spacing: 8, children: [
                      OutlinedButton(onPressed: () => _note(c), child: const Text('Add observation')),
                      PopupMenuButton<String>(
                        onSelected: (s) => _status(c, s),
                        itemBuilder: (_) => [for (final e in _statuses.entries) PopupMenuItem(value: e.key, child: Text(e.value))],
                        child: const Chip(label: Text('Change status')),
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
        loading: 'Loading activity…',
        load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/cases/$caseId/notes')),
        builder: (context, d) {
          final notes = asMaps(d['items']);
          if (notes.isEmpty) return const Padding(padding: EdgeInsets.all(8), child: Text('No activity recorded yet.'));
          return Column(children: [
            for (final n in notes)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text(str(n['note'])),
                subtitle: Text('Observed ${displayDate(str(n['observed_on']))} · farmer reported'),
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
  static const _labels = {'active': 'Start / resume', 'paused': 'Pause', 'completed': 'Mark complete', 'cancelled': 'Cancel plan'};

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
    final v = await showFormSheet(context, title: 'New plan', fields: const [
      FieldSpec('title', 'Plan title', required: true, maxLength: 160),
      FieldSpec('objective', 'Goal', kind: FieldKind.multiline, maxLength: 2000),
      FieldSpec('steps', 'Steps (one per line)', kind: FieldKind.multiline),
    ]);
    if (v == null || !mounted) return;
    final steps = '${v['steps'] ?? ''}'.split('\n').map((s) => s.trim()).where((s) => s.isNotEmpty).take(30)
        .map((s) => {'title': s, 'done': false}).toList();
    await notebookWrite(context, ref,
        (api) => api.post('/api/farm-workspace/missions', body: {'title': v['title'], 'objective': v['objective'] ?? '', 'steps': steps}),
        done: 'Plan saved as a draft.', reload: _loader);
  }

  @override
  Widget build(BuildContext context) {
    final assistant = ref.watch(assistantProvider);
    return Loader<Map<String, dynamic>>(
      key: _loader,
      loading: 'Loading your farm plans…',
      load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/missions')),
      builder: (context, d) {
        final items = asMaps(d['items']);
        return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
          SectionTitle('Your farm plans', trailing: FilledButton.tonalIcon(onPressed: _create, icon: const Icon(Icons.add), label: const Text('New plan'))),
          if (str(d['note']).isNotEmpty) Text(str(d['note']), style: TextStyle(fontSize: 12, color: mutedColor(context))),
          if (items.isEmpty) const EmptyView(title: 'Nothing saved here yet.', detail: 'Approve a Saathi suggestion or add a plan.'),
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
        subtitle: Text('${status[0].toUpperCase()}${status.substring(1)} · $done of ${steps.length} steps confirmed by you'),
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
                  : (v) => _save(m, steps: [
                        for (var j = 0; j < steps.length; j++) j == i ? {...steps[j], 'done': v ?? false} : steps[j],
                      ]),
              title: Text(str(steps[i]['title'])),
            ),
          Wrap(spacing: 8, runSpacing: 6, children: [
            for (final next in _transitions[status] ?? const <String>[])
              OutlinedButton(
                onPressed: next == 'completed' && done < steps.length ? null : () => _save(m, status: next),
                child: Text(_labels[next]!),
              ),
            if (status == 'active' || status == 'draft')
              FilledButton.tonal(
                onPressed: assistant.busy || assistant.pending != null
                    ? null
                    : () {
                        ref.read(assistantProvider.notifier).send(
                              'Help me work on my farm plan “${m['title']}”. Tell me which steps remain and what I can do next.',
                              context: RunContext(view: 'records', missionId: str(m['id'])),
                            );
                        context.push('/chat');
                      },
                child: const Text('Work on this with Mitra'),
              ),
          ]),
          if (done < steps.length && status == 'active')
            Padding(
              padding: const EdgeInsets.all(8),
              child: Text('Confirm every step before marking the plan complete.', style: TextStyle(fontSize: 11.5, color: mutedColor(context))),
            ),
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
        title: const Text('Progress and activity', style: TextStyle(fontSize: 13)),
        children: [
          Loader<Map<String, dynamic>>(
            loading: 'Loading activity…',
            load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/missions/$missionId/receipts')),
            builder: (context, d) {
              final items = asMaps(d['items']);
              if (items.isEmpty) return const Padding(padding: EdgeInsets.all(8), child: Text('No activity recorded yet.'));
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
        loading: 'Loading saved facts…',
        load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/memories')),
        builder: (context, d) {
          final items = asMaps(d['items']);
          return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
            const SectionTitle('Your farm details'),
            if (str(d['note']).isNotEmpty) Text(str(d['note']), style: TextStyle(fontSize: 12, color: mutedColor(context))),
            if (items.isEmpty) const EmptyView(title: 'No saved farm facts yet.', detail: 'Mitra remembers details you tell it in chat.'),
            for (final m in items)
              Card(
                child: ListTile(
                  title: Text(_value(m['value'])),
                  subtitle: Text('${str(m['fact_key']).replaceAll('.', ' · ')} · since ${displayDate(str(m['valid_from']))}'),
                  trailing: PopupMenuButton<String>(
                    onSelected: (action) async {
                      if (action == 'forget') {
                        if (!await confirmAction(context,
                            title: 'Forget this saved fact?',
                            body: 'Its original conversation may still exist.',
                            confirm: 'Confirm forget')) {
                          return;
                        }
                        if (!context.mounted) return;
                        await notebookWrite(context, ref, (api) => api.delete('/api/farm-workspace/memories/${m['id']}'),
                            done: 'Fact forgotten.', reload: _loader);
                      } else {
                        final v = await showFormSheet(context, title: 'Correct this fact', fields: [
                          FieldSpec('value', 'Correct value', kind: FieldKind.multiline, required: true, initial: _value(m['value']), maxLength: 2000),
                        ]);
                        if (v == null || !context.mounted) return;
                        await notebookWrite(context, ref, (api) => api.patch('/api/farm-workspace/memories/${m['id']}', body: v),
                            done: 'Correction saved.', reload: _loader);
                      }
                    },
                    itemBuilder: (_) => const [
                      PopupMenuItem(value: 'correct', child: Text('Correct')),
                      PopupMenuItem(value: 'forget', child: Text('Forget')),
                    ],
                  ),
                ),
              ),
          ]);
        },
      );
}
