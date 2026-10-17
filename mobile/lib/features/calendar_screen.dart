import '../tour/app_tour.dart';
import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../assistant/assistant_controller.dart';
import '../assistant/helper_sheet.dart';
import '../assistant/models.dart';
import '../core/api.dart';
import '../ui/kit.dart';
import '../utils/constants.dart';
import '../voice/voice_button.dart';
import 'saathi.dart';
import 'starter_plans.dart';

/// Saved farm tasks by day. A task here is a plan, not proof of work or a
/// scheduled notification.
class CalendarScreen extends ConsumerStatefulWidget {
  const CalendarScreen({super.key});

  @override
  ConsumerState<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends ConsumerState<CalendarScreen> {
  DateTime _month = DateTime(DateTime.now().year, DateTime.now().month);
  DateTime _selected = DateUtils.dateOnly(DateTime.now());
  bool _saving = false;

  Future<void> _change(FarmTask task,
      {bool delete = false, bool restore = false}) async {
    setState(() => _saving = true);
    try {
      await ref
          .read(assistantProvider.notifier)
          .changeTask(task, delete: delete, restore: restore);
      if (!mounted) return;
      if (delete) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('fos.farm.task_removed'.tr()),
          action: SnackBarAction(
              label: 'fos.farm.undo'.tr(),
              onPressed: () => _change(task, restore: true)),
        ));
      }
    } on ApiException catch (e) {
      if (mounted) showNotice(context, e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _edit(FarmTask task) async {
    final updated = await showModalBottomSheet<FarmTask>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => _TaskEditor(task: task),
    );
    if (updated != null) await _change(updated);
  }

  bool _monthView = true;

  Widget _taskCard(FarmTask t, bool locked, {bool overdue = false}) {
    final ink = inkColor(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: FarmCard(
        child: Row(children: [
          Expanded(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(t.title,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                    color: ink,
                    decoration: t.completed ? TextDecoration.lineThrough : null,
                  )),
              if (t.notes.isNotEmpty && t.notes != 'Demo plan: no real work has been executed')
                Text(t.notes,
                    style: TextStyle(fontSize: 13, color: mutedColor(context))),
              const SizedBox(height: 4),
              if (overdue)
                Tag(
                    'fos.farm2.cal_due_on'
                        .tr(namedArgs: {'date': displayDate(t.dueDate)}),
                    color: AppColors.warning)
              else
                Tag(
                    t.completed
                        ? 'fos.farm.done'.tr()
                        : 'fos.farm.planned'.tr(),
                    color:
                        t.completed ? AppColors.primaryDark : AppColors.info),
            ]),
          ),
          if (!t.completed)
            IconButton(
              tooltip: 'fos.farm.mark_done'.tr(),
              onPressed: locked
                  ? null
                  : () {
                      HapticFeedback.selectionClick();
                      _change(t.copyWith(completed: true));
                    },
              icon: const Icon(Icons.check_circle_outline),
            ),
          PopupMenuButton<String>(
            enabled: !locked,
            tooltip: 'fos.farm.task_options'.tr(),
            onSelected: (v) =>
                v == 'edit' ? _edit(t) : _change(t, delete: true),
            itemBuilder: (_) => [
              PopupMenuItem(value: 'edit', child: Text('fos.farm.edit'.tr())),
              PopupMenuItem(
                  value: 'delete', child: Text('fos.farm.remove'.tr())),
            ],
          ),
        ]),
      ),
    );
  }

  String _dayName(DateTime d, DateTime today) {
    final lang = context.locale.languageCode;
    final full = DateFormat.MMMEd(lang).format(d);
    final diff = DateUtils.dateOnly(d).difference(today).inDays;
    if (diff == 0) return '${'fos.farm2.cal_today'.tr()} · $full';
    if (diff == 1) return '${'fos.farm2.cal_tomorrow'.tr()} · $full';
    return full;
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(assistantProvider);
    final locked = _saving || state.busy || state.pending != null;
    final byDay = <String, List<FarmTask>>{};
    for (final t in state.tasks) {
      byDay.putIfAbsent(t.dueDate, () => []).add(t);
    }
    final key = isoDate(_selected);
    final today = DateUtils.dateOnly(DateTime.now());
    final todayKey = isoDate(today);
    final selectedTasks = byDay[key] ?? const [];
    final runContext = RunContext(view: 'calendar', selectedDate: key);
    final loading = !state.ready && state.loading;

    Widget addButton(String forKey) => TourAnchor(id: 'add-task', child: FilledButton.tonalIcon(
          onPressed: locked
              ? null
              : () => ref
                      .read(assistantProvider.notifier)
                      .send(
                          'Help me add a farm task for $forKey. Ask what I need to do.',
                          context: runContext)
                      .then((_) {
                    if (context.mounted) {
                      showHelperSheet(context, 'calendar',
                          runContext: runContext);
                    }
                  }),
          icon: const Icon(Icons.add),
          label: Text('fos.farm.add'.tr()),
        ));

    final toggle = TourAnchor(id: 'calendar-view', child: FilledButton.tonalIcon(
      onPressed: () => setState(() => _monthView = !_monthView),
      icon: Icon(_monthView
          ? Icons.view_agenda_outlined
          : Icons.calendar_month_outlined),
      label: Text(_monthView
          ? 'fos.farm2.cal_week_view'.tr()
          : 'fos.farm2.cal_month_view'.tr()),
    ));

    final children = <Widget>[];
    if (_monthView) {
      children.addAll([
        _MonthGrid(
          month: _month,
          selected: _selected,
          byDay: byDay,
          onMonth: (m) => setState(() => _month = m),
          onSelect: (d) => setState(() => _selected = d),
        ),
        SectionTitle(displayDate(key)),
        Wrap(spacing: 8, runSpacing: 8, children: [toggle, addButton(key)]),
        const SizedBox(height: 8),
        if (loading)
          LoadingView('fos.farm.loading'.tr())
        else if (selectedTasks.isEmpty)
          EmptyView(title: 'fos.farm.no_tasks_day'.tr())
        else
          for (final t in selectedTasks) _taskCard(t, locked),
      ]);
    } else {
      final overdue = state.tasks
          .where((t) => !t.completed && t.dueDate.compareTo(todayKey) < 0)
          .toList()
        ..sort((a, b) => a.dueDate.compareTo(b.dueDate));
      final emptyDays = <String>[];
      final lang = context.locale.languageCode;
      final dayWidgets = <Widget>[];
      for (var i = 0; i < 7; i++) {
        final d = DateTime(today.year, today.month, today.day + i);
        final tasks = byDay[isoDate(d)] ?? const [];
        if (tasks.isEmpty) {
          emptyDays.add(i == 0
              ? 'fos.farm2.cal_today'.tr()
              : DateFormat.MMMEd(lang).format(d));
          continue;
        }
        dayWidgets.add(SectionTitle(_dayName(d, today)));
        dayWidgets.addAll([for (final t in tasks) _taskCard(t, locked)]);
      }
      children.addAll([
        SectionTitle('fos.farm2.cal_this_week'.tr()),
        Wrap(
            spacing: 8, runSpacing: 8, children: [toggle, addButton(todayKey)]),
        if (loading) LoadingView('fos.farm.loading'.tr()),
        if (!loading && overdue.isNotEmpty) ...[
          SectionTitle('fos.farm2.cal_overdue'.tr()),
          for (final t in overdue) _taskCard(t, locked, overdue: true),
        ],
        if (!loading) ...dayWidgets,
        if (!loading && emptyDays.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: FarmCard(
              child: Text(
                  '${'fos.farm2.cal_no_work'.tr()}: ${emptyDays.join(', ')}',
                  style: TextStyle(fontSize: 14, color: mutedColor(context))),
            ),
          ),
      ]);
    }
    return Scaffold(
      appBar: AppBar(title: Text('fos.farm.calendar'.tr()), actions: [
          const TourReplayButton(),
        TourAnchor(id: 'deleted', child: IconButton(
          tooltip: 'fos.farm.deleted_tasks'.tr(),
          icon: const Icon(Icons.restore_from_trash_outlined),
          onPressed: () => _showDeleted(context),
        )),
      ]),
      floatingActionButton:
          HelperButton(contextKey: 'calendar', runContext: runContext),
      body: FarmBackground(
        child: RefreshIndicator(
          onRefresh: ref.read(assistantProvider.notifier).refresh,
          child: ListView(
                  key: const PageStorageKey('calendar'),
              padding: const EdgeInsets.fromLTRB(0, 8, 0, 96),
              children: [
                const FeatureIntro(
                    eyebrow: 'MY TASKS',
                    title: 'Room for a good day.',
                    detail: 'Make a little plan. Keep track of what matters.',
                    icon: Icons.event_available_outlined),
                ...children,
                const SizedBox(height: 16),
                const PreparedBySaathi(area: 'today'),
                if (state.ready && state.tasks.isEmpty) const StarterPlans()
              ].map((child) => Padding(padding: EdgeInsets.symmetric(horizontal: child is _MonthGrid && MediaQuery.sizeOf(context).width < 400 ? 4 : 24), child: child)).toList()),
        ),
      ),
    );
  }

  void _showDeleted(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      builder: (_) => Consumer(builder: (context, ref, _) {
        final deleted =
            ref.watch(assistantProvider.select((s) => s.deletedTasks));
        return ListView(
            shrinkWrap: true,
            padding: const EdgeInsets.all(12),
            children: [
              ListTile(
                  title: Text('fos.farm.removed_tasks'.tr(),
                      style: const TextStyle(fontWeight: FontWeight.w700))),
              if (deleted.isEmpty)
                EmptyView(title: 'fos.farm.no_deleted_tasks'.tr()),
              for (final t in deleted)
                ListTile(
                  title: Text(t.title),
                  subtitle: Text(displayDate(t.dueDate)),
                  trailing: TextButton(
                      onPressed: () => _change(t, restore: true),
                      child: Text('fos.farm.restore'.tr())),
                ),
            ]);
      }),
    );
  }
}

class _MonthGrid extends StatelessWidget {
  const _MonthGrid({
    required this.month,
    required this.selected,
    required this.byDay,
    required this.onMonth,
    required this.onSelect,
  });

  final DateTime month;
  final DateTime selected;
  final Map<String, List<FarmTask>> byDay;
  final ValueChanged<DateTime> onMonth;
  final ValueChanged<DateTime> onSelect;

  @override
  Widget build(BuildContext context) {
    final first = DateTime(month.year, month.month);
    final start =
        first.subtract(Duration(days: first.weekday - 1)); // Monday first
    final today = DateUtils.dateOnly(DateTime.now());
    final ink = inkColor(context);
    final lang = context.locale.languageCode;
    return FarmCard(
      padding: const EdgeInsets.all(8),
      child: Column(children: [
        Row(children: [
          IconButton(
            tooltip: 'fos.farm.previous_month'.tr(),
            onPressed: () => onMonth(DateTime(month.year, month.month - 1)),
            icon: const Icon(Icons.chevron_left),
          ),
          Expanded(
            child: Text(DateFormat.yMMMM(lang).format(month),
                textAlign: TextAlign.center,
                style: TextStyle(fontWeight: FontWeight.w700, color: ink)),
          ),
          IconButton(
            tooltip: 'fos.farm.next_month'.tr(),
            onPressed: () => onMonth(DateTime(month.year, month.month + 1)),
            icon: const Icon(Icons.chevron_right),
          ),
        ]),
        Row(children: [
          for (var i = 0; i < 7; i++)
            Expanded(
                child: Center(
                    child: Text(
                        DateFormat('EEEEE', lang)
                            .format(DateTime(2024, 1, 1 + i)),
                        style: TextStyle(
                            fontSize: 11, color: mutedColor(context))))),
        ]),
        for (var week = 0; week < 6; week++)
          Row(children: [
            for (var day = 0; day < 7; day++)
              Expanded(
                  child: _cell(
                      context,
                      DateTime(
                          start.year, start.month, start.day + week * 7 + day),
                      today)),
          ]),
      ]),
    );
  }

  Widget _cell(BuildContext context, DateTime d, DateTime today) {
    final tasks = byDay[isoDate(d)] ?? const [];
    final isSelected = DateUtils.isSameDay(d, selected);
    final inMonth = d.month == month.month;
    final open = tasks.where((t) => !t.completed).length;
    return Semantics(
      button: true,
      selected: isSelected,
      label: 'fos.farm.day_tasks'.tr(namedArgs: {
        'date': displayDate(isoDate(d)),
        'count': '${tasks.length}'
      }),
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: () {
          HapticFeedback.selectionClick();
          onSelect(d);
        },
        child: Container(
          height: 48,
          margin: const EdgeInsets.all(1.5),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.primary : null,
            borderRadius: BorderRadius.circular(10),
            border: DateUtils.isSameDay(d, today)
                ? Border.all(color: AppColors.primaryDark)
                : null,
          ),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Text('${d.day}',
                style: TextStyle(
                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w400,
                  color: isSelected
                      ? Colors.white
                      : inMonth
                          ? inkColor(context)
                          : mutedColor(context).withValues(alpha: 0.5),
                )),
            if (tasks.isNotEmpty)
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                for (var i = 0; i < tasks.length.clamp(0, 3); i++)
                  Container(
                    width: 5,
                    height: 5,
                    margin: const EdgeInsets.symmetric(horizontal: 1),
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: isSelected
                          ? Colors.white
                          : i < open
                              ? AppColors.warning
                              : AppColors.primaryDark,
                    ),
                  ),
              ]),
          ]),
        ),
      ),
    );
  }
}

class _TaskEditor extends StatefulWidget {
  const _TaskEditor({required this.task});

  final FarmTask task;

  @override
  State<_TaskEditor> createState() => _TaskEditorState();
}

class _TaskEditorState extends State<_TaskEditor> {
  late final _title = TextEditingController(text: widget.task.title);
  late final _notes = TextEditingController(text: widget.task.notes);
  late String _date = widget.task.dueDate;
  late bool _done = widget.task.completed;
  String? _error;

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.fromLTRB(
            16, 16, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('fos.farm.edit_task'.tr(),
                  style: TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w700,
                      color: inkColor(context))),
              TextField(
                controller: _title,
                maxLength: 200,
                decoration: InputDecoration(
                  labelText: 'fos.farm.task'.tr(),
                  suffixIcon: VoiceButton(onTranscript: (t) => _title.text = t),
                ),
              ),
              TextField(
                controller: _notes,
                maxLength: 2000,
                maxLines: 3,
                decoration: InputDecoration(
                  labelText: 'fos.farm.notes'.tr(),
                  suffixIcon: VoiceButton(
                      onTranscript: (t) =>
                          _notes.text = '${_notes.text} $t'.trim()),
                ),
              ),
              FilledButton.tonalIcon(
                icon: const Icon(Icons.event),
                label: Text(displayDate(_date)),
                onPressed: () async {
                  final picked = await showDatePicker(
                    context: context,
                    initialDate: DateTime.tryParse(_date) ?? DateTime.now(),
                    firstDate: DateTime(2020),
                    lastDate: DateTime(2100),
                  );
                  if (picked != null) setState(() => _date = isoDate(picked));
                },
              ),
              CheckboxListTile(
                contentPadding: EdgeInsets.zero,
                value: _done,
                onChanged: (v) => setState(() => _done = v ?? false),
                title: Text('fos.farm.i_have_done_this'.tr()),
              ),
              if (_error != null)
                Text(_error!, style: const TextStyle(color: AppColors.error)),
              Row(mainAxisAlignment: MainAxisAlignment.end, children: [
                TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: Text('fos.farm.cancel'.tr())),
                FilledButton(
                  onPressed: () {
                    HapticFeedback.selectionClick();
                    if (_title.text.trim().isEmpty) {
                      return setState(
                          () => _error = 'fos.farm.add_task_title'.tr());
                    }
                    Navigator.pop(
                      context,
                      widget.task.copyWith(
                          title: _title.text.trim(),
                          notes: _notes.text.trim(),
                          dueDate: _date,
                          completed: _done),
                    );
                  },
                  child: Text('fos.farm.save'.tr()),
                ),
              ]),
            ]),
      );
}
