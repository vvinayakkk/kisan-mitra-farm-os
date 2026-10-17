import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../assistant/assistant_controller.dart';
import '../../assistant/helper_sheet.dart';
import '../../assistant/widgets/farm_result.dart';
import '../../core/session.dart';
import '../../ui/kit.dart';
import '../../ui/loader.dart';
import '../../ui/provenance.dart';
import '../../utils/constants.dart';
import '../saathi.dart';
import '../workspace_tools.dart';
import 'fields_tab.dart';
import 'records_tabs.dart';

const kNotebookTabs = <(String, String, String)>[
  // (tab id, label translation key, helper context)
  ('today', 'fos.notebook.tab_today', 'today'),
  ('fields', 'fos.notebook.tab_fields', 'fields'),
  ('ledger', 'fos.notebook.tab_money', 'ledger'),
  ('cases', 'fos.notebook.tab_followups', 'followups'),
  ('missions', 'fos.notebook.tab_plans', 'missions'),
  ('memory', 'fos.notebook.tab_memory', 'memory'),
  ('files', 'fos.notebook.tab_files', 'records'),
];

class NotebookScreen extends StatefulWidget {
  const NotebookScreen({super.key, this.initialTab});

  final String? initialTab;

  @override
  State<NotebookScreen> createState() => _NotebookScreenState();
}

class _NotebookScreenState extends State<NotebookScreen> with SingleTickerProviderStateMixin {
  late final _tabs = TabController(
    length: kNotebookTabs.length,
    vsync: this,
    initialIndex: kNotebookTabs.indexWhere((t) => t.$1 == widget.initialTab).clamp(0, kNotebookTabs.length - 1),
  )..addListener(() => setState(() {}));

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final helper = kNotebookTabs[_tabs.index].$3;
    return Scaffold(
      appBar: AppBar(
        title: Text('fos.notebook.notebook'.tr()),
        bottom: TabBar(
          controller: _tabs,
          isScrollable: true,
          tabAlignment: TabAlignment.start,
          labelColor: accentColor(context),
          unselectedLabelColor: mutedColor(context),
          tabs: [for (final t in kNotebookTabs) Tab(text: t.$2.tr())],
        ),
      ),
      floatingActionButton: HelperButton(key: ValueKey(helper), contextKey: helper),
      body: FarmBackground(
        child: TabBarView(controller: _tabs, children: const [
          TodayTab(),
          FieldsTab(),
          LedgerTab(),
          CasesTab(),
          MissionsTab(),
          MemoryTab(),
          FilesTab(),
        ]),
      ),
    );
  }
}

class TodayTab extends ConsumerWidget {
  const TodayTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.watch(apiProvider);
    final ink = inkColor(context);
    return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
      const PreparedBySaathi(area: 'records'),
      Loader<Map<String, dynamic>>(
        loading: 'fos.notebook.loading'.tr(),
        load: () async => asMap(await api.get('/api/farm-workspace/today')),
        builder: (context, d) {
          final actions = asMaps(d['actions']);
          final counts = asMap(d['counts']);
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(
                child: Text('fos.notebook.counts_summary'.tr(namedArgs: {'tasks': '${counts['tasks'] ?? 0}', 'cases': '${counts['cases'] ?? 0}', 'plans': '${counts['missions'] ?? 0}'}), style: TextStyle(color: mutedColor(context))),
              ),
              ProvenanceBadge.maybe(d['provenance']) ?? const SizedBox.shrink(),
            ]),
            const SizedBox(height: 8),
            if (actions.isEmpty)
              EmptyView(title: 'fos.notebook.nothing_urgent'.tr())
            else
              for (final a in actions)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: FarmCard(
                    onTap: () => context.push(switch (a['kind']) {
                      'task' => '/calendar',
                      'crop_case' => '/notebook?tab=cases',
                      _ => '/chat',
                    }),
                    child: Row(children: [
                      Icon(a['kind'] == 'task' ? Icons.event_note : Icons.local_florist_outlined, color: accentColor(context)),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(str(a['title']), style: TextStyle(fontWeight: FontWeight.w600, color: ink)),
                          Text(
                            str(a['detail']).replaceAllMapped(
                                RegExp(r'\d{4}-\d{2}-\d{2}T[\d:.+]+(Z|[+-]\d{2}:\d{2})?'), (m) => displayDate(m.group(0))),
                            style: TextStyle(fontSize: 12.5, color: mutedColor(context)),
                          ),
                        ]),
                      ),
                      const Icon(Icons.chevron_right),
                    ]),
                  ),
                ),
          ]);
        },
      ),
      SectionTitle('fos.notebook.weather'.tr()),
      Loader<Map<String, dynamic>>(
        loading: 'fos.notebook.loading'.tr(),
        load: () async => asMap(await api.get('/api/farm-workspace/weather-brief')),
        builder: (context, d) {
          final signals = asMaps(d['signals']).take(6).toList();
          if (d['available'] != true) {
            return Text(str(d['message'], 'fos.notebook.weather_unavailable'.tr()),
                style: TextStyle(color: mutedColor(context)));
          }
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (signals.isEmpty)
              Text('fos.notebook.no_weather_flags'.tr(),
                  style: TextStyle(color: mutedColor(context))),
            for (final s in signals)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(s['kind'] == 'rain' ? Icons.umbrella_outlined : Icons.wb_sunny_outlined, color: AppColors.warning),
                title: Text(str(s['title'])),
                subtitle: Text('${displayDate(str(s['date']))} · ${str(s['detail'])}'),
              ),
            Tag('fos.notebook.forecast'.tr(), color: AppColors.info),
          ]);
        },
      ),
      SectionTitle('fos.notebook.recent_records'.tr()),
      Loader<Map<String, dynamic>>(
        loading: 'fos.notebook.loading'.tr(),
        load: () async => asMap(await api.get('/api/farm-workspace/timeline', query: {'limit': 30})),
        builder: (context, d) {
          final items = asMaps(d['items']);
          if (items.isEmpty) return EmptyView(title: 'fos.notebook.no_records'.tr());
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            for (final i in items.take(12))
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text(str(i['title'])),
                subtitle: Text('${displayDate(str(i['occurred_at']))} · ${str(i['kind']).replaceAll('_', ' ')}'
                    '${asMap(i['detail'])['status'] != null ? ' · ${asMap(i['detail'])['status']}' : ''}'),
                trailing: asMap(i['detail'])['origin'] == null ? null : ProvenanceBadge({'origin': asMap(i['detail'])['origin']}),
              ),
          ]);
        },
      ),
    ]);
  }
}

class FilesTab extends ConsumerWidget {
  const FilesTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final artifacts = ref.watch(assistantProvider.select((s) => s.artifacts));
    final running = ref.watch(assistantProvider.select((s) => s.running));
    return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
      SectionTitle('fos.notebook.saved_files'.tr()),
      if (artifacts.isEmpty)
        EmptyView(title: 'fos.notebook.no_saved_files'.tr())
      else
        for (final a in artifacts) FileResult(a),
      SectionTitle('fos.notebook.recent_costs'.tr()),
      Loader<Map<String, dynamic>>(
        key: ValueKey(running),
        loading: 'fos.notebook.loading'.tr(),
        load: () => ref.read(workspaceToolsProvider).inspect('list_expenses', {}),
        builder: (context, d) {
          final expenses = asMaps(d['expenses']);
          if (expenses.isEmpty) {
            return EmptyView(title: 'fos.notebook.no_expenses'.tr());
          }
          final total = expenses.fold<num>(0, (s, e) => s + ((e['amount'] as num?) ?? 0));
          return Column(children: [
            for (final e in expenses)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text(str(e['description'])),
                subtitle: Text(displayDate(str(e['date']))),
                trailing: Text('₹${e['amount']}'),
              ),
            Align(alignment: Alignment.centerRight, child: Text('fos.notebook.total'.tr(namedArgs: {'amount': total.toStringAsFixed(2)}))),
          ]);
        },
      ),
    ]);
  }
}
