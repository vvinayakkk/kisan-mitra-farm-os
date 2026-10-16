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
  // (tab id, label, helper context)
  ('today', 'Today', 'today'),
  ('fields', 'My fields', 'fields'),
  ('ledger', 'Money', 'ledger'),
  ('cases', 'Crop follow-ups', 'followups'),
  ('missions', 'Plans', 'missions'),
  ('memory', 'Memory', 'memory'),
  ('files', 'Files', 'records'),
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
    final ink = inkColor(context);
    final helper = kNotebookTabs[_tabs.index].$3;
    return Scaffold(
      appBar: AppBar(
        title: Text('My farm notebook', style: TextStyle(color: ink)),
        foregroundColor: ink,
        bottom: TabBar(
          controller: _tabs,
          isScrollable: true,
          tabAlignment: TabAlignment.start,
          labelColor: AppColors.primaryDark,
          unselectedLabelColor: mutedColor(context),
          tabs: [for (final t in kNotebookTabs) Tab(text: t.$2)],
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
        loading: 'Gathering your saved farm activity…',
        load: () async => asMap(await api.get('/api/farm-workspace/today')),
        builder: (context, d) {
          final actions = asMaps(d['actions']);
          final counts = asMap(d['counts']);
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(
                child: Text('${counts['tasks'] ?? 0} open tasks · ${counts['cases'] ?? 0} crop follow-ups · '
                    '${counts['missions'] ?? 0} ongoing plans', style: TextStyle(color: mutedColor(context))),
              ),
              ProvenanceBadge.maybe(d['provenance']) ?? const SizedBox.shrink(),
            ]),
            const SizedBox(height: 8),
            if (actions.isEmpty)
              const EmptyView(title: 'No urgent saved work.', detail: 'Add your field or plan your next farm task with Mitra.')
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
                      Icon(a['kind'] == 'task' ? Icons.event_note : Icons.local_florist_outlined, color: AppColors.primaryDark),
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
            Text('Based on your saved tasks and crop follow-ups.', style: TextStyle(fontSize: 11.5, color: mutedColor(context))),
          ]);
        },
      ),
      const SectionTitle('Weather to plan around'),
      Loader<Map<String, dynamic>>(
        loading: 'Reading the dated forecast…',
        load: () async => asMap(await api.get('/api/farm-workspace/weather-brief')),
        builder: (context, d) {
          final signals = asMaps(d['signals']).take(6).toList();
          if (d['available'] != true) {
            return Text(str(d['message'], 'Weather context is unavailable. Link a field to the forecast grid.'),
                style: TextStyle(color: mutedColor(context)));
          }
          return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (signals.isEmpty)
              Text('No additional weather flags in this dated forecast. Check its dates before planning field work.',
                  style: TextStyle(color: mutedColor(context))),
            for (final s in signals)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: Icon(s['kind'] == 'rain' ? Icons.umbrella_outlined : Icons.wb_sunny_outlined, color: AppColors.warning),
                title: Text(str(s['title'])),
                subtitle: Text('${displayDate(str(s['date']))} · ${str(s['detail'])}'),
              ),
            const Tag('Forecast', color: AppColors.info),
            if (str(d['note']).isNotEmpty)
              Text(str(d['note']), style: TextStyle(fontSize: 11.5, color: mutedColor(context))),
          ]);
        },
      ),
      const SectionTitle('Recent records'),
      Loader<Map<String, dynamic>>(
        loading: 'Loading dated records…',
        load: () async => asMap(await api.get('/api/farm-workspace/timeline', query: {'limit': 30})),
        builder: (context, d) {
          final items = asMaps(d['items']);
          if (items.isEmpty) return const EmptyView(title: 'No dated farm records yet.');
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
            Text('Calendar dates describe plans; they do not prove work was performed.',
                style: TextStyle(fontSize: 11.5, color: mutedColor(context))),
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
      const SectionTitle('Saved files'),
      if (artifacts.isEmpty)
        const EmptyView(title: 'Your notebook has room to grow.', detail: 'Ask Mitra for a report, sheet or slide deck.')
      else
        for (final a in artifacts) FileResult(a),
      const SectionTitle('Latest recorded costs'),
      Loader<Map<String, dynamic>>(
        key: ValueKey(running),
        loading: 'Loading saved costs…',
        load: () => ref.read(workspaceToolsProvider).inspect('list_expenses', {}),
        builder: (context, d) {
          final expenses = asMaps(d['expenses']);
          if (expenses.isEmpty) {
            return const EmptyView(
                title: 'No saved expenses yet.', detail: 'Ask Mitra to record a cost; you’ll review it before it is saved.');
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
            Align(alignment: Alignment.centerRight, child: Text('Total recorded ₹${total.toStringAsFixed(2)}')),
          ]);
        },
      ),
    ]);
  }
}
