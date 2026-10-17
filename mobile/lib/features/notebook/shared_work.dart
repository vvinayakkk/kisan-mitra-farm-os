import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/session.dart';
import '../../ui/form_sheet.dart';
import '../../ui/kit.dart';
import '../../ui/loader.dart';
import 'records_tabs.dart';

/// Service arrangements and family/FPO group checklists. Everything here is
/// the farmer's own record; no supplier is contacted and nothing is booked.
class SharedFarmWork extends ConsumerStatefulWidget {
  const SharedFarmWork({super.key});

  @override
  ConsumerState<SharedFarmWork> createState() => _SharedFarmWorkState();
}

class _SharedFarmWorkState extends ConsumerState<SharedFarmWork> {
  final _services = GlobalKey<LoaderState<Map<String, dynamic>>>();
  final _groups = GlobalKey<LoaderState<Map<String, dynamic>>>();

  static const _types = {'labour': 'Labour', 'machinery': 'Machinery', 'transport': 'Transport', 'expert': 'Expert', 'other': 'Other'};
  static const _statuses = {
    'planned': 'Planning',
    'requested': 'Request recorded',
    'quote_recorded': 'Quote recorded',
    'farmer_confirmed': 'You confirmed',
    'farmer_completed': 'You marked complete',
    'cancelled': 'Cancelled',
  };

  Future<void> _service([Map<String, dynamic>? s]) async {
    final v = await showFormSheet(context,
        title: s == null ? 'New arrangement' : 'Update arrangement',
        note: 'Your own record; nothing is booked.',
        fields: [
          FieldSpec('title', 'What do you need', required: true, initial: s?['title'], maxLength: 160),
          FieldSpec('service_type', 'Type', kind: FieldKind.select, required: true, initial: s?['service_type'] ?? 'labour', options: _types),
          FieldSpec('supplier', 'Supplier', initial: s?['supplier'], maxLength: 160),
          FieldSpec('quote_inr', 'Quote you received (₹)', kind: FieldKind.number, initial: s?['quote_inr']),
          FieldSpec('scheduled_on', 'Planned date', kind: FieldKind.date, initial: s?['scheduled_on']),
          FieldSpec('status', 'Status', kind: FieldKind.select, required: true, initial: s?['status'] ?? 'planned', options: _statuses),
          FieldSpec('notes', 'Notes', kind: FieldKind.multiline, initial: s?['notes'], maxLength: 2000),
        ]);
    if (v == null || !mounted) return;
    final body = {...v, 'supplier': v['supplier'] ?? '', 'notes': v['notes'] ?? ''};
    await notebookWrite(context, ref, (api) async {
      if (s == null) {
        await api.post('/api/farm-workspace/service-requests', body: body);
      } else {
        await api.patch('/api/farm-workspace/service-requests/${s['id']}', body: {...body, 'row_version': s['row_version']});
      }
    }, done: 'Arrangement saved.', reload: _services);
  }

  Future<void> _group({bool join = false}) async {
    final v = await showFormSheet(context,
        title: join ? 'Join a group' : 'Create a group',
        fields: join
            ? const [
                FieldSpec('code', 'Invite code', required: true),
                FieldSpec('consent', 'Share my display name with this group', kind: FieldKind.check),
              ]
            : const [FieldSpec('name', 'Group name', required: true, maxLength: 100)]);
    if (v == null || !mounted) return;
    if (join && v['consent'] != true) return showNotice(context, 'Consent needed to join.');
    await notebookWrite(context, ref, (api) async {
      if (join) {
        await api.post('/api/farm-workspace/groups/join', body: {'code': v['code'], 'consent_to_share_display_name': true});
      } else {
        await api.post('/api/farm-workspace/groups', body: {'name': v['name']});
      }
    }, done: join ? 'Joined group.' : 'Group created.', reload: _groups);
  }

  @override
  Widget build(BuildContext context) {
    final api = ref.watch(apiProvider);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionTitle('Service arrangements',
          trailing: FilledButton.tonalIcon(onPressed: _service, icon: const Icon(Icons.add), label: const Text('Add'))),
      Loader<Map<String, dynamic>>(
        key: _services,
        loading: 'Loading…',
        load: () async => asMap(await api.get('/api/farm-workspace/service-requests')),
        builder: (context, d) {
          final items = asMaps(d['items']);
          if (items.isEmpty) return const EmptyView(title: 'No arrangements yet.');
          return Column(children: [
            for (final s in items)
              Card(
                child: ListTile(
                  title: Text(str(s['title'])),
                  subtitle: Text([
                    _statuses[s['status']] ?? str(s['status']),
                    if (str(s['supplier']).isNotEmpty) str(s['supplier']),
                    if (s['quote_inr'] != null) '${rupees(s['quote_inr'])} quote',
                    if (s['scheduled_on'] != null) 'Planned ${displayDate(str(s['scheduled_on']))}',
                  ].join(' · ')),
                  onTap: () => _service(s),
                ),
              ),
          ]);
        },
      ),
      SectionTitle('Family & FPO groups',
          trailing: Row(mainAxisSize: MainAxisSize.min, children: [
            FilledButton.tonal(onPressed: () => _group(join: true), child: const Text('Join')),
            const SizedBox(width: 6),
            FilledButton.tonal(onPressed: _group, child: const Text('Create')),
          ])),
      Loader<Map<String, dynamic>>(
        key: _groups,
        loading: 'Loading…',
        load: () async => asMap(await api.get('/api/farm-workspace/groups')),
        builder: (context, d) {
          final items = asMaps(d['items']);
          if (items.isEmpty) {
            return const EmptyView(title: 'No groups yet.');
          }
          return Column(children: [for (final g in items) _GroupCard(group: g)]);
        },
      ),
    ]);
  }
}

class _GroupCard extends ConsumerStatefulWidget {
  const _GroupCard({required this.group});

  final Map<String, dynamic> group;

  @override
  ConsumerState<_GroupCard> createState() => _GroupCardState();
}

class _GroupCardState extends ConsumerState<_GroupCard> {
  final _tasks = GlobalKey<LoaderState<Map<String, dynamic>>>();

  String get _gid => str(widget.group['id']);
  String get _role => str(widget.group['role']);

  Future<void> _invite() async {
    final v = await showFormSheet(context, title: 'Invite to ${widget.group['name']}', fields: const [
      FieldSpec('role', 'Their role', kind: FieldKind.select, required: true, initial: 'reader',
          options: {'reader': 'Can view', 'contributor': 'Can add and edit tasks'}),
      FieldSpec('consent', 'Share this group’s plans with the person who uses the code', kind: FieldKind.check),
    ]);
    if (v == null || !mounted) return;
    if (v['consent'] != true) return showNotice(context, 'Consent needed to invite.');
    try {
      final r = asMap(await ref.read(apiProvider).post('/api/farm-workspace/groups/$_gid/invites',
          body: {'role': v['role'], 'consent_to_share_group_plans': true}));
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('One-time invite code'),
          content: SelectableText('${r['code']}\n\nValid until ${displayDate(str(r['expires_at']), withTime: true)}.'),
          actions: [
            TextButton(
              onPressed: () => Clipboard.setData(ClipboardData(text: str(r['code']))),
              child: const Text('Copy'),
            ),
            FilledButton(onPressed: () => Navigator.pop(c), child: const Text('Done')),
          ],
        ),
      );
    } catch (e) {
      if (mounted) showNotice(context, '$e');
    }
  }

  Future<void> _task([Map<String, dynamic>? t]) async {
    final v = await showFormSheet(context, title: t == null ? 'New group task' : 'Edit group task', fields: [
      FieldSpec('title', 'Task', required: true, initial: t?['title'], maxLength: 160),
      FieldSpec('notes', 'Notes', kind: FieldKind.multiline, initial: t?['notes'], maxLength: 2000),
      FieldSpec('due_on', 'Due', kind: FieldKind.date, initial: t?['due_on']),
    ]);
    if (v == null || !mounted) return;
    await notebookWrite(context, ref, (api) async {
      final body = {...v, 'notes': v['notes'] ?? ''};
      if (t == null) {
        await api.post('/api/farm-workspace/groups/$_gid/tasks', body: body);
      } else {
        await api.patch('/api/farm-workspace/groups/$_gid/tasks/${t['id']}',
            body: {...body, 'completed': t['completed'] == true, 'row_version': t['row_version']});
      }
    }, reload: _tasks);
  }

  @override
  Widget build(BuildContext context) {
    final canEdit = _role == 'owner' || _role == 'contributor';
    return Card(
      child: ExpansionTile(
        shape: const Border(),
        title: Text(str(widget.group['name'])),
        subtitle: Text(_role),
        childrenPadding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
        children: [
          Loader<Map<String, dynamic>>(
            key: _tasks,
            loading: 'Loading…',
            load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/groups/$_gid/tasks')),
            builder: (context, d) {
              final items = asMaps(d['items']);
              if (items.isEmpty) return const Padding(padding: EdgeInsets.all(8), child: Text('No tasks yet.'));
              return Column(children: [
                for (final t in items)
                  CheckboxListTile(
                    value: t['completed'] == true,
                    onChanged: !canEdit
                        ? null
                        : (v) {
                            HapticFeedback.selectionClick();
                            notebookWrite(
                              context,
                              ref,
                              (api) => api.patch('/api/farm-workspace/groups/$_gid/tasks/${t['id']}', body: {
                                'title': t['title'],
                                'notes': t['notes'] ?? '',
                                'due_on': t['due_on'],
                                'completed': v ?? false,
                                'row_version': t['row_version'],
                              }),
                              reload: _tasks,
                            );
                          },
                    title: Text(str(t['title'])),
                    subtitle: t['due_on'] == null ? null : Text('Due ${displayDate(str(t['due_on']))}'),
                    secondary: canEdit ? IconButton(icon: const Icon(Icons.edit_outlined), onPressed: () => _task(t)) : null,
                  ),
              ]);
            },
          ),
          Wrap(spacing: 8, children: [
            if (canEdit) FilledButton.tonal(onPressed: _task, child: const Text('Add task')),
            if (_role == 'owner') FilledButton.tonal(onPressed: _invite, child: const Text('Invite')),
          ]),
        ],
      ),
    );
  }
}
