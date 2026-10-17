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

  Future<void> _change(FarmTask task, {bool delete = false, bool restore = false}) async {
    setState(() => _saving = true);
    try {
      await ref.read(assistantProvider.notifier).changeTask(task, delete: delete, restore: restore);
      if (!mounted) return;
      if (delete) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: const Text('Task removed.'),
          action: SnackBarAction(label: 'Undo', onPressed: () => _change(task, restore: true)),
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

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(assistantProvider);
    final locked = _saving || state.busy || state.pending != null;
    final byDay = <String, List<FarmTask>>{};
    for (final t in state.tasks) {
      byDay.putIfAbsent(t.dueDate, () => []).add(t);
    }
    final key = isoDate(_selected);
    final today = byDay[key] ?? const [];
    final ink = inkColor(context);
    final runContext = RunContext(view: 'calendar', selectedDate: key);
    return Scaffold(
      appBar: AppBar(title: const Text('Calendar'), actions: [
        IconButton(
          tooltip: 'Deleted tasks',
          icon: const Icon(Icons.restore_from_trash_outlined),
          onPressed: () => _showDeleted(context),
        ),
      ]),
      floatingActionButton: HelperButton(contextKey: 'calendar', runContext: runContext),
      body: FarmBackground(
        child: RefreshIndicator(
          onRefresh: ref.read(assistantProvider.notifier).refresh,
          child: ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 96), children: [
            const PreparedBySaathi(area: 'today'),
            _MonthGrid(
              month: _month,
              selected: _selected,
              byDay: byDay,
              onMonth: (m) => setState(() => _month = m),
              onSelect: (d) => setState(() => _selected = d),
            ),
            SectionTitle(displayDate(key),
                trailing: FilledButton.tonalIcon(
                  onPressed: locked
                      ? null
                      : () => ref.read(assistantProvider.notifier).send(
                          'Help me add a farm task for $key. Ask what I need to do.',
                          context: runContext).then((_) {
                            if (context.mounted) showHelperSheet(context, 'calendar', runContext: runContext);
                          }),
                  icon: const Icon(Icons.add),
                  label: const Text('Add'),
                )),
            if (!state.ready && state.loading)
              const LoadingView('Loading…')
            else if (today.isEmpty)
              const EmptyView(title: 'No tasks this day.')
            else
              for (final t in today)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: FarmCard(
                    child: Row(children: [
                      Expanded(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(t.title,
                              style: TextStyle(
                                fontWeight: FontWeight.w600,
                                color: ink,
                                decoration: t.completed ? TextDecoration.lineThrough : null,
                              )),
                          if (t.notes.isNotEmpty)
                            Text(t.notes, style: TextStyle(fontSize: 12.5, color: mutedColor(context))),
                          const SizedBox(height: 4),
                          Tag(t.completed ? 'Done' : 'Planned',
                              color: t.completed ? AppColors.primaryDark : AppColors.info),
                        ]),
                      ),
                      if (!t.completed)
                        IconButton(
                          tooltip: 'Mark done',
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
                        tooltip: 'Task options',
                        onSelected: (v) => v == 'edit' ? _edit(t) : _change(t, delete: true),
                        itemBuilder: (_) => const [
                          PopupMenuItem(value: 'edit', child: Text('Edit')),
                          PopupMenuItem(value: 'delete', child: Text('Remove')),
                        ],
                      ),
                    ]),
                  ),
                ),
          ]),
        ),
      ),
    );
  }

  void _showDeleted(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      builder: (_) => Consumer(builder: (context, ref, _) {
        final deleted = ref.watch(assistantProvider.select((s) => s.deletedTasks));
        return ListView(shrinkWrap: true, padding: const EdgeInsets.all(12), children: [
          const ListTile(title: Text('Removed tasks', style: TextStyle(fontWeight: FontWeight.w700))),
          if (deleted.isEmpty) const EmptyView(title: 'No deleted tasks.'),
          for (final t in deleted)
            ListTile(
              title: Text(t.title),
              subtitle: Text(displayDate(t.dueDate)),
              trailing: TextButton(onPressed: () => _change(t, restore: true), child: const Text('Restore')),
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
    final start = first.subtract(Duration(days: first.weekday - 1)); // Monday first
    final today = DateUtils.dateOnly(DateTime.now());
    final ink = inkColor(context);
    const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    return FarmCard(
      padding: const EdgeInsets.all(8),
      child: Column(children: [
        Row(children: [
          IconButton(
            tooltip: 'Previous month',
            onPressed: () => onMonth(DateTime(month.year, month.month - 1)),
            icon: const Icon(Icons.chevron_left),
          ),
          Expanded(
            child: Text('${months[month.month - 1]} ${month.year}',
                textAlign: TextAlign.center, style: TextStyle(fontWeight: FontWeight.w700, color: ink)),
          ),
          IconButton(
            tooltip: 'Next month',
            onPressed: () => onMonth(DateTime(month.year, month.month + 1)),
            icon: const Icon(Icons.chevron_right),
          ),
        ]),
        Row(children: [
          for (final d in const ['M', 'T', 'W', 'T', 'F', 'S', 'S'])
            Expanded(child: Center(child: Text(d, style: TextStyle(fontSize: 11, color: mutedColor(context))))),
        ]),
        for (var week = 0; week < 6; week++)
          Row(children: [
            for (var day = 0; day < 7; day++)
              Expanded(child: _cell(context, DateTime(start.year, start.month, start.day + week * 7 + day), today)),
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
      label: '${displayDate(isoDate(d))}, ${tasks.length} tasks',
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: () {
          HapticFeedback.selectionClick();
          onSelect(d);
        },
        child: Container(
          height: 44,
          margin: const EdgeInsets.all(1.5),
          decoration: BoxDecoration(
            color: isSelected ? AppColors.primary : null,
            borderRadius: BorderRadius.circular(10),
            border: DateUtils.isSameDay(d, today) ? Border.all(color: AppColors.primaryDark) : null,
          ),
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Text('${d.day}',
                style: TextStyle(
                  fontWeight: isSelected ? FontWeight.w700 : FontWeight.w400,
                  color: isSelected ? Colors.white : inMonth ? inkColor(context) : mutedColor(context).withValues(alpha: 0.5),
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
        padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Edit task', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
          TextField(
            controller: _title,
            maxLength: 200,
            decoration: InputDecoration(
              labelText: 'Task',
              suffixIcon: VoiceButton(onTranscript: (t) => _title.text = t),
            ),
          ),
          TextField(
            controller: _notes,
            maxLength: 2000,
            maxLines: 3,
            decoration: InputDecoration(
              labelText: 'Notes',
              suffixIcon: VoiceButton(onTranscript: (t) => _notes.text = '${_notes.text} $t'.trim()),
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
            title: const Text('I have done this'),
          ),
          if (_error != null) Text(_error!, style: const TextStyle(color: AppColors.error)),
          Row(mainAxisAlignment: MainAxisAlignment.end, children: [
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
            FilledButton(
              onPressed: () {
                HapticFeedback.selectionClick();
                if (_title.text.trim().isEmpty) return setState(() => _error = 'Add a task title.');
                Navigator.pop(
                  context,
                  widget.task.copyWith(title: _title.text.trim(), notes: _notes.text.trim(), dueDate: _date, completed: _done),
                );
              },
              child: const Text('Save'),
            ),
          ]),
        ]),
      );
}
