import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/session.dart';
import '../../ui/form_sheet.dart';
import '../../ui/kit.dart';
import '../../ui/labels.dart';
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

  Map<String, String> get _types => {'labour': 'fos.notebook.svc_labour'.tr(), 'machinery': 'fos.notebook.svc_machinery'.tr(), 'transport': 'fos.notebook.svc_transport'.tr(), 'expert': 'fos.notebook.svc_expert'.tr(), 'other': 'fos.notebook.other'.tr()};
  Map<String, String> get _statuses => {
        for (final k in const ['planned', 'requested', 'quote_recorded', 'farmer_confirmed', 'farmer_completed', 'cancelled']) k: statusLabel(k)
      };

  Future<void> _service([Map<String, dynamic>? s]) async {
    final v = await showFormWithDetails(context,
        title: s == null ? 'fos.notebook.new_arrangement'.tr() : 'fos.notebook.update_arrangement'.tr(),
        note: 'fos.notebook.arrangement_note'.tr(),
        hasExtra: s != null && (str(s['supplier']).isNotEmpty || s['quote_inr'] != null || s['scheduled_on'] != null || str(s['notes']).isNotEmpty),
        main: [
          FieldSpec('title', 'fos.notebook.what_need'.tr(), required: true, initial: s?['title'], maxLength: 160),
          FieldSpec('service_type', 'fos.notebook.type'.tr(), kind: FieldKind.select, required: true, initial: s?['service_type'] ?? 'labour', options: _types),
          FieldSpec('status', 'fos.notebook.status'.tr(), kind: FieldKind.select, required: true, initial: s?['status'] ?? 'planned', options: _statuses),
        ],
        extra: [
          FieldSpec('supplier', 'fos.notebook.supplier'.tr(), initial: s?['supplier'], maxLength: 160),
          FieldSpec('quote_inr', 'fos.notebook.quote_received'.tr(), kind: FieldKind.number, initial: s?['quote_inr']),
          FieldSpec('scheduled_on', 'fos.notebook.planned_date'.tr(), kind: FieldKind.date, initial: s?['scheduled_on']),
          FieldSpec('notes', 'fos.notebook.notes'.tr(), kind: FieldKind.multiline, initial: s?['notes'], maxLength: 2000),
        ]);
    if (v == null || !mounted) return;
    final body = {...v, 'supplier': v['supplier'] ?? '', 'notes': v['notes'] ?? ''};
    await notebookWrite(context, ref, (api) async {
      if (s == null) {
        await api.post('/api/farm-workspace/service-requests', body: body);
      } else {
        await api.patch('/api/farm-workspace/service-requests/${s['id']}', body: {...body, 'row_version': s['row_version']});
      }
    }, done: 'fos.notebook.arrangement_saved'.tr(), reload: _services);
  }

  Future<void> _group({bool join = false}) async {
    final v = await showFormSheet(context,
        title: join ? 'fos.notebook.join_group'.tr() : 'fos.notebook.create_group'.tr(),
        fields: join
            ? [
                FieldSpec('code', 'fos.notebook.invite_code'.tr(), required: true),
                FieldSpec('consent', 'fos.notebook.share_name_consent'.tr(), kind: FieldKind.check),
              ]
            : [FieldSpec('name', 'fos.notebook.group_name'.tr(), required: true, maxLength: 100)]);
    if (v == null || !mounted) return;
    if (join && v['consent'] != true) return showNotice(context, 'fos.notebook.consent_join'.tr());
    await notebookWrite(context, ref, (api) async {
      if (join) {
        await api.post('/api/farm-workspace/groups/join', body: {'code': v['code'], 'consent_to_share_display_name': true});
      } else {
        await api.post('/api/farm-workspace/groups', body: {'name': v['name']});
      }
    }, done: join ? 'fos.notebook.joined_group'.tr() : 'fos.notebook.group_created'.tr(), reload: _groups);
  }

  @override
  Widget build(BuildContext context) {
    final api = ref.watch(apiProvider);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionTitle('fos.notebook.service_arrangements'.tr(),
          trailing: FilledButton.tonalIcon(onPressed: _service, icon: const Icon(Icons.add), label: Text('fos.notebook.add'.tr()))),
      Loader<Map<String, dynamic>>(
        key: _services,
        loading: 'fos.notebook.loading'.tr(),
        load: () async => asMap(await api.get('/api/farm-workspace/service-requests')),
        builder: (context, d) {
          final items = asMaps(d['items']);
          if (items.isEmpty) return EmptyView(title: 'fos.notebook.no_arrangements'.tr());
          return Column(children: [
            for (final s in items)
              Card(
                child: ListTile(
                  title: Text(str(s['title'])),
                  subtitle: Text([
                    statusLabel(s['status']),
                    if (str(s['supplier']).isNotEmpty) str(s['supplier']),
                    if (s['quote_inr'] != null) 'fos.notebook.quote_suffix'.tr(namedArgs: {'amount': rupees(s['quote_inr'])}),
                    if (s['scheduled_on'] != null) 'fos.notebook.planned_on'.tr(namedArgs: {'date': displayDate(str(s['scheduled_on']))}),
                  ].join(' · ')),
                  onTap: () => _service(s),
                ),
              ),
          ]);
        },
      ),
      SectionTitle('fos.notebook.family_fpo_groups'.tr(),
          trailing: Row(mainAxisSize: MainAxisSize.min, children: [
            FilledButton.tonal(onPressed: () => _group(join: true), child: Text('fos.notebook.join'.tr())),
            const SizedBox(width: 6),
            FilledButton.tonal(onPressed: _group, child: Text('fos.notebook.create'.tr())),
          ])),
      Loader<Map<String, dynamic>>(
        key: _groups,
        loading: 'fos.notebook.loading'.tr(),
        load: () async => asMap(await api.get('/api/farm-workspace/groups')),
        builder: (context, d) {
          final items = asMaps(d['items']);
          if (items.isEmpty) {
            return EmptyView(title: 'fos.notebook.no_groups'.tr());
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
  String get _roleName => switch (_role) {
        'owner' => 'fos.notebook2.role_owner'.tr(),
        'contributor' => 'fos.notebook.can_edit'.tr(),
        'reader' => 'fos.notebook.can_view'.tr(),
        _ => humanize(_role),
      };

  Future<void> _invite() async {
    final v = await showFormSheet(context, title: 'fos.notebook.invite_to'.tr(namedArgs: {'group': '${widget.group['name']}'}), fields: [
      FieldSpec('role', 'fos.notebook.their_role'.tr(), kind: FieldKind.select, required: true, initial: 'reader',
          options: {'reader': 'fos.notebook.can_view'.tr(), 'contributor': 'fos.notebook.can_edit'.tr()}),
      FieldSpec('consent', 'fos.notebook.share_plans_consent'.tr(), kind: FieldKind.check),
    ]);
    if (v == null || !mounted) return;
    if (v['consent'] != true) return showNotice(context, 'fos.notebook.consent_invite'.tr());
    try {
      final r = asMap(await ref.read(apiProvider).post('/api/farm-workspace/groups/$_gid/invites',
          body: {'role': v['role'], 'consent_to_share_group_plans': true}));
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (c) => AlertDialog(
          title: Text('fos.notebook.invite_code_title'.tr()),
          content: SelectableText('${r['code']}\n\n${'fos.notebook.valid_until'.tr(namedArgs: {'date': displayDate(str(r['expires_at']), withTime: true)})}'),
          actions: [
            TextButton(
              onPressed: () => Clipboard.setData(ClipboardData(text: str(r['code']))),
              child: Text('fos.notebook.copy'.tr()),
            ),
            FilledButton(onPressed: () => Navigator.pop(c), child: Text('fos.notebook.done'.tr())),
          ],
        ),
      );
    } catch (e) {
      if (mounted) showNotice(context, '$e');
    }
  }

  Future<void> _task([Map<String, dynamic>? t]) async {
    final v = await showFormSheet(context, title: t == null ? 'fos.notebook.new_group_task'.tr() : 'fos.notebook.edit_group_task'.tr(), fields: [
      FieldSpec('title', 'fos.notebook.task'.tr(), required: true, initial: t?['title'], maxLength: 160),
      FieldSpec('notes', 'fos.notebook.notes'.tr(), kind: FieldKind.multiline, initial: t?['notes'], maxLength: 2000),
      FieldSpec('due_on', 'fos.notebook.due'.tr(), kind: FieldKind.date, initial: t?['due_on']),
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
        subtitle: Text(_roleName),
        childrenPadding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
        children: [
          Loader<Map<String, dynamic>>(
            key: _tasks,
            loading: 'fos.notebook.loading'.tr(),
            load: () async => asMap(await ref.read(apiProvider).get('/api/farm-workspace/groups/$_gid/tasks')),
            builder: (context, d) {
              final items = asMaps(d['items']);
              if (items.isEmpty) return Padding(padding: const EdgeInsets.all(8), child: Text('fos.notebook.no_tasks'.tr()));
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
                    subtitle: t['due_on'] == null ? null : Text('fos.notebook.due_on'.tr(namedArgs: {'date': displayDate(str(t['due_on']))})),
                    secondary: canEdit ? IconButton(icon: const Icon(Icons.edit_outlined), onPressed: () => _task(t)) : null,
                  ),
              ]);
            },
          ),
          Wrap(spacing: 8, children: [
            if (canEdit) FilledButton.tonal(onPressed: _task, child: Text('fos.notebook.add_task'.tr())),
            if (_role == 'owner') FilledButton.tonal(onPressed: _invite, child: Text('fos.notebook.invite'.tr())),
          ]),
        ],
      ),
    );
  }
}
