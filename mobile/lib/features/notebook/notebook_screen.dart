import '../../tour/app_tour.dart';
import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../assistant/assistant_controller.dart';
import '../../assistant/helper_sheet.dart';
import '../../assistant/widgets/farm_result.dart';
import '../../core/session.dart';
import '../../ui/kit.dart';
import '../../ui/labels.dart';
import '../../ui/loader.dart';
import '../../ui/provenance.dart';
import '../../utils/constants.dart';
import '../saathi.dart';
import '../starter_plans.dart';
import '../workspace_tools.dart';
import 'fields_tab.dart';
import 'records_tabs.dart';

const kNotebookTabs = <(String, String, String)>[
  // (tab id, label translation key, helper context)
  ('today', 'fos.notebook.tab_today', 'today'),
  ('fields', 'fos.notebook.tab_fields', 'fields'),
  ('ledger', 'fos.notebook.tab_money', 'ledger'),
  ('cases', 'fos.notebook2.tab_crop_checks', 'followups'),
  ('missions', 'fos.notebook.tab_plans', 'missions'),
  ('more', 'fos.notebook2.tab_more', 'records'),
];

// Old links used separate Memory and Files tabs; both now live under More.
String? _tabAlias(String? id) =>
    (id == 'memory' || id == 'files') ? 'more' : id;

class NotebookScreen extends StatefulWidget {
  const NotebookScreen({super.key, this.initialTab});

  final String? initialTab;

  @override
  State<NotebookScreen> createState() => _NotebookScreenState();
}

class _NotebookScreenState extends State<NotebookScreen>
    with SingleTickerProviderStateMixin {
  late final _tabs = TabController(
    length: kNotebookTabs.length,
    vsync: this,
    initialIndex: kNotebookTabs
        .indexWhere((t) => t.$1 == _tabAlias(widget.initialTab))
        .clamp(0, kNotebookTabs.length - 1),
  )..addListener(() => setState(() {}));

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final helper = kNotebookTabs[_tabs.index].$3;
    return TourSection(scope: 'notebook-$helper', child: Scaffold(
      appBar: AppBar(
        actions: const [TourReplayButton()],
        title: Text('fos.notebook.notebook'.tr()),
        bottom: PreferredSize(preferredSize: const Size.fromHeight(48), child: TourAnchor(id: 'tabs', child: TabBar(
          controller: _tabs,
          isScrollable: true,
          tabAlignment: TabAlignment.start,
          labelColor: accentColor(context),
          unselectedLabelColor: mutedColor(context),
          tabs: [for (final t in kNotebookTabs) Tab(text: t.$2.tr())],
        ))),
      ),
      floatingActionButton:
          HelperButton(key: ValueKey(helper), contextKey: helper),
      body: FarmBackground(
        child: TabBarView(controller: _tabs, children: const [
          TodayTab(),
          FieldsTab(),
          LedgerTab(),
          CasesTab(),
          MissionsTab(),
          MoreTab(),
        ]),
      ),
    ));
  }
}

final _isoStamp = RegExp(r'\d{4}-\d{2}-\d{2}(T[\d:.+]+(Z|[+-]\d{2}:\d{2})?)?');

/// One plain line per action, composed here so the server's English text never shows.
String _actionLine(Map<String, dynamic> a, Map<String, dynamic> counts) {
  switch (a['kind']) {
    case 'task':
      final m = _isoStamp.firstMatch(str(a['detail']));
      final due = m == null ? null : DateTime.tryParse(m.group(0)!);
      if (due == null) return '';
      // Compare calendar days: a task due today is not overdue.
      final day = DateUtils.dateOnly(due.toLocal());
      final today = DateUtils.dateOnly(DateTime.now());
      if (day == today) return 'fos.label.due_today'.tr();
      return (day.isBefore(today)
              ? 'fos.notebook2.today_overdue'
              : 'fos.notebook2.today_due')
          .tr(namedArgs: {'date': displayDate(m!.group(0))});
    case 'crop_case':
      return 'fos.notebook2.today_cases_open'
          .tr(namedArgs: {'n': '${counts['cases'] ?? '—'}'});
    default:
      return '';
  }
}

class TodayTab extends ConsumerWidget {
  const TodayTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final api = ref.watch(apiProvider);
    final ink = inkColor(context);
    return ListView(
                  key: const PageStorageKey('notebook-today'),
        padding: const EdgeInsets.fromLTRB(24, 12, 24, 96),
        children: [
          const FeatureIntro(
              eyebrow: 'FARM NOTEBOOK',
              title: 'A place for every little detail.',
              detail:
                  'Your fields, money and plans. Kept together, ready when you need them.',
              icon: Icons.menu_book_outlined),

          const PreparedBySaathi(area: 'records'),
          Loader<Map<String, dynamic>>(
            loading: 'fos.notebook.loading'.tr(),
            load: () async => asMap(await api.get('/api/farm-workspace/today')),
            builder: (context, d) {
              final actions = asMaps(d['actions']);
              final counts = asMap(d['counts']);
              return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(children: [
                      Expanded(
                        child: Text(
                            'fos.notebook2.counts_summary'.tr(namedArgs: {
                              'tasks': '${counts['tasks'] ?? '—'}',
                              'cases': '${counts['cases'] ?? '—'}',
                              'plans': '${counts['missions'] ?? '—'}'
                            }),
                            style: TextStyle(
                                fontSize: 14, color: mutedColor(context))),
                      ),
                      ProvenanceBadge.maybe(d['provenance']) ??
                          const SizedBox.shrink(),
                    ]),
                    const SizedBox(height: 8),
                    if (actions.isEmpty)
                      const StarterPlans()
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
                              Icon(
                                  a['kind'] == 'task'
                                      ? Icons.event_note
                                      : Icons.local_florist_outlined,
                                  color: accentColor(context)),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(str(a['title']),
                                          style: TextStyle(
                                              fontWeight: FontWeight.w600,
                                              color: ink)),
                                      if (_actionLine(a, counts).isNotEmpty)
                                        Text(_actionLine(a, counts),
                                            style: TextStyle(
                                                fontSize: 13,
                                                color: mutedColor(context))),
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
            load: () async =>
                asMap(await api.get('/api/farm-workspace/weather-brief')),
            builder: (context, d) {
              final signals = asMaps(d['signals']).take(6).toList();
              if (d['available'] != true) {
                return Text(
                    str(d['message'], 'fos.notebook.weather_unavailable'.tr()),
                    style: TextStyle(color: mutedColor(context)));
              }
              return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (signals.isEmpty)
                      Text('fos.notebook.no_weather_flags'.tr(),
                          style: TextStyle(color: mutedColor(context))),
                    for (final s in signals)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(
                            s['kind'] == 'rain'
                                ? Icons.umbrella_outlined
                                : Icons.wb_sunny_outlined,
                            color: AppColors.warning),
                        title: Text(str(s['title'])),
                        subtitle: Text(
                            '${displayDate(str(s['date']))} · ${str(s['detail'])}'),
                      ),
                    Tag('fos.notebook.forecast'.tr(), color: AppColors.info),
                  ]);
            },
          ),
          SectionTitle('fos.notebook.recent_records'.tr()),
          Loader<Map<String, dynamic>>(
            loading: 'fos.notebook.loading'.tr(),
            load: () async => asMap(await api
                .get('/api/farm-workspace/timeline', query: {'limit': 30})),
            builder: (context, d) {
              final items = asMaps(d['items']);
              if (items.isEmpty) {
                return EmptyView(title: 'fos.notebook.no_records'.tr());
              }
              return Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    for (final i in items.take(12))
                      ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        title: Text(str(i['title'])),
                        subtitle: Text(
                            '${displayDate(str(i['occurred_at']))} · ${kindLabel(i['kind'])}'
                            '${asMap(i['detail'])['status'] != null ? ' · ${statusLabel(asMap(i['detail'])['status'])}' : ''}'),
                        trailing: asMap(i['detail'])['origin'] == null
                            ? null
                            : ProvenanceBadge(
                                {'origin': asMap(i['detail'])['origin']}),
                      ),
                  ]);
            },
          ),
        ]);
  }
}

/// Memory and Files together, as two sections.
class MoreTab extends StatelessWidget {
  const MoreTab({super.key});

  @override
  Widget build(BuildContext context) => ListView(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 96),
          children: const [
            MemorySection(),
            FilesSection(),
          ]);
}

class FilesSection extends ConsumerWidget {
  const FilesSection({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final artifacts = ref.watch(assistantProvider.select((s) => s.artifacts));
    final running = ref.watch(assistantProvider.select((s) => s.running));
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionTitle('fos.notebook2.reports_files'.tr()),
      if (artifacts.isEmpty)
        EmptyView(title: 'fos.notebook.no_saved_files'.tr())
      else
        for (final a in artifacts) FileResult(a),
      SectionTitle('fos.notebook.recent_costs'.tr()),
      Loader<Map<String, dynamic>>(
        key: ValueKey(running),
        loading: 'fos.notebook.loading'.tr(),
        load: () =>
            ref.read(workspaceToolsProvider).inspect('list_expenses', {}),
        builder: (context, d) {
          final expenses = asMaps(d['expenses']);
          if (expenses.isEmpty) {
            return EmptyView(title: 'fos.notebook.no_expenses'.tr());
          }
          final total =
              expenses.fold<num>(0, (s, e) => s + ((e['amount'] as num?) ?? 0));
          return Column(children: [
            for (final e in expenses)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text(str(e['description'])),
                subtitle: Text(displayDate(str(e['date']))),
                trailing: Text(rupees(e['amount']),
                    style: const TextStyle(fontSize: 14)),
              ),
            Align(
                alignment: Alignment.centerRight,
                child: Text(
                    'fos.notebook.total'.tr(namedArgs: {'amount': inr(total)}),
                    style: const TextStyle(fontWeight: FontWeight.w600))),
          ]);
        },
      ),
    ]);
  }
}
