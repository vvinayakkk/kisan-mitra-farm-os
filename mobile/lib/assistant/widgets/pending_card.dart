import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/api.dart';
import '../../ui/kit.dart';
import '../../utils/constants.dart';
import '../../voice/voice_button.dart';
import '../assistant_controller.dart';
import '../models.dart';

/// The paused run: one focused question at a time, or one exact change to
/// approve or decline. Nothing is saved until the farmer acts here.
class PendingCard extends ConsumerWidget {
  const PendingCard({super.key, required this.pending});

  final Pending pending;

  @override
  Widget build(BuildContext context, WidgetRef ref) => pending.kind == PendingKind.approval
      ? ApprovalCard(pending: pending)
      : QuestionFlow(key: ValueKey(pending.id), pending: pending);
}

const _approvalPrompts = {
  'save_task': 'Add this task to your farm plan?',
  'record_expense': 'Save this expense to your records?',
  'update_task': 'Save these changes to your task?',
  'delete_task': 'Remove this task from your plan? It can be restored.',
  'complete_task': 'Mark this task complete in your plan?',
  'record_ledger': 'Save this entry to your farm ledger?',
  'create_crop_case': 'Open this crop follow-up?',
  'record_crop_note': 'Save this dated crop observation?',
  'create_mission': 'Save this longer farm plan?',
  'record_service': 'Save your service arrangement? No booking or payment is made.',
  'create_farm_group': 'Create this private group checklist? No one is invited yet.',
  'create_shared_task': 'Save this task for the selected group’s members to see?',
  'save_soil_report':
      'Save these report values? Check sample date, depth, units and nutrient basis. This does not verify the laboratory.',
};

const _fieldLabels = {
  'task_id': 'Task',
  'plot_id': 'Field',
  'group_id': 'Group',
  'case_id': 'Crop follow-up',
  'attachment_id': 'Source report',
  'amount_inr': 'Amount (rupees)',
  'quote_inr': 'Quoted amount (rupees)',
};

const _leading = ['title', 'description', 'amount_inr', 'due_date', 'occurred_on'];

/// Most identifying fields first, so the card reads like a sentence.
List<MapEntry<String, dynamic>> orderedArguments(Map<String, dynamic> args) => args.entries.toList()
  ..sort((a, b) {
    int rank(String k) => _leading.contains(k) ? _leading.indexOf(k) : _leading.length;
    return rank(a.key).compareTo(rank(b.key));
  });

String reviewValue(Object? v) {
  if (v == null || v == '') return 'Not provided';
  if (v is String && RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(v)) return displayDate(v);
  if (v is bool) return v ? 'Yes' : 'No';
  if (v is List) return v.take(36).map(reviewValue).join('\n');
  if (v is Map) {
    if (v['title'] != null) return '${v['title']}${v['done'] == true ? ' · completed' : ''}';
    if (v['property'] != null) {
      return '${'${v['property']}'.replaceAll('_', ' ')} · ${v['value']} ${v['unit_code'] ?? ''} '
          '(${v['reported_basis'] ?? ''}, depth ${v['depth_top_cm']}–${v['depth_bottom_cm']} cm)';
    }
    return v.entries.take(20).map((e) => '${'${e.key}'.replaceAll('_', ' ')}: ${reviewValue(e.value)}').join(' · ');
  }
  return '$v';
}

class ApprovalCard extends ConsumerWidget {
  const ApprovalCard({super.key, required this.pending});

  final Pending pending;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tasks = ref.watch(assistantProvider.select((s) => s.tasks));
    final controller = ref.read(assistantProvider.notifier);
    final ink = inkColor(context);
    final confirm = switch (pending.tool) {
      'delete_task' => 'Remove task',
      'update_task' => 'Save changes',
      'complete_task' => 'Mark complete',
      _ => 'Save it',
    };
    return _CardFrame(
      icon: Icons.fact_check_outlined,
      heading: 'REVIEW BEFORE SAVING',
      children: [
        Text(_approvalPrompts[pending.tool] ?? 'Save this reviewed change?',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: ink)),
        const SizedBox(height: 10),
        for (final e in orderedArguments(pending.arguments))
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(_fieldLabels[e.key] ?? e.key.replaceAll('_', ' '),
                  style: TextStyle(fontSize: 12, color: mutedColor(context))),
              Text(
                pending.reviewLabels[e.key] ??
                    (e.key == 'task_id'
                        ? tasks.where((t) => t.id == e.value).map((t) => t.title).firstOrNull ?? 'Selected farm task'
                        : reviewValue(e.value)),
                style: TextStyle(fontSize: 14.5, color: ink),
              ),
            ]),
          ),
        Text('Saving changes only your Kisan Mitra records. No message, booking or field work happens.',
            style: TextStyle(fontSize: 11.5, color: mutedColor(context))),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(
            child: OutlinedButton(onPressed: () => controller.decline(pending), child: const Text('Don’t save')),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: FilledButton.icon(
              onPressed: () => controller.approve(pending),
              icon: const Icon(Icons.check, size: 18),
              label: Text(confirm),
            ),
          ),
        ]),
      ],
    );
  }
}

class QuestionFlow extends ConsumerStatefulWidget {
  const QuestionFlow({super.key, required this.pending});

  final Pending pending;

  @override
  ConsumerState<QuestionFlow> createState() => _QuestionFlowState();
}

class _QuestionFlowState extends ConsumerState<QuestionFlow> {
  final _values = <String, String>{};
  final _text = TextEditingController();
  int _step = 0;
  String? _error;
  bool _uploading = false;

  List<QuestionField> get _fields => widget.pending.fields;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  void _syncText() {
    final field = _fields[_step];
    if (field.type != 'select' && field.type != 'photo') _values[field.id] = _text.text.trim();
  }

  void _goto(int step) {
    setState(() {
      _step = step;
      _error = null;
      _text.text = _values[_fields[step].id] ?? '';
    });
  }

  String? _validate(QuestionField f) {
    final v = _values[f.id]?.trim() ?? '';
    if (v.isEmpty) return 'Add this detail to continue.';
    if (f.type == 'number' && num.tryParse(v) == null) return 'Enter a number.';
    if (f.type == 'date' && DateTime.tryParse(v) == null) return 'Choose a date.';
    return null;
  }

  void _next() {
    _syncText();
    final error = _validate(_fields[_step]);
    if (error != null) return setState(() => _error = error);
    if (_step < _fields.length - 1) return _goto(_step + 1);
    ref.read(assistantProvider.notifier).answer(widget.pending, Map.of(_values));
  }

  Future<void> _photo(ImageSource source) async {
    final picked = await ImagePicker().pickImage(source: source, maxWidth: 2048, imageQuality: 85);
    if (picked == null) return;
    setState(() => _uploading = true);
    try {
      final attachment =
          await ref.read(assistantProvider.notifier).uploadBytes(picked.name, await picked.readAsBytes());
      setState(() {
        _values[_fields[_step].id] = attachment.id;
        _error = null;
      });
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_fields.isEmpty) return const SizedBox.shrink();
    final field = _fields[_step];
    final ink = inkColor(context);
    final photos = ref.watch(assistantProvider.select((s) => s.attachments.where((a) => a.isPhoto).toList()));
    return _CardFrame(
      icon: Icons.auto_awesome,
      heading: 'MITRA NEEDS A DETAIL',
      trailing: _fields.length > 1 ? Text('${_step + 1} / ${_fields.length}', style: TextStyle(color: mutedColor(context))) : null,
      children: [
        if (_fields.length > 1)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: LinearProgressIndicator(value: (_step + 1) / _fields.length, minHeight: 3),
          ),
        if (widget.pending.question != null && _step == 0)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Text(widget.pending.question!, style: TextStyle(color: mutedColor(context))),
          ),
        Text(field.prompt, style: TextStyle(fontSize: 15.5, fontWeight: FontWeight.w600, color: ink)),
        const SizedBox(height: 10),
        switch (field.type) {
          'select' => Wrap(spacing: 8, runSpacing: 8, children: [
              for (final o in field.options)
                ChoiceChip(
                  label: Text(o),
                  selected: _values[field.id] == o,
                  onSelected: (_) => setState(() {
                    _values[field.id] = o;
                    _error = null;
                  }),
                ),
            ]),
          'photo' => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Wrap(spacing: 8, children: [
                OutlinedButton.icon(
                    onPressed: _uploading ? null : () => _photo(ImageSource.camera),
                    icon: const Icon(Icons.photo_camera_outlined),
                    label: const Text('Take photo')),
                OutlinedButton.icon(
                    onPressed: _uploading ? null : () => _photo(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('Choose photo')),
              ]),
              if (_uploading) const LinearProgressIndicator(),
              if (photos.isNotEmpty)
                DropdownButton<String>(
                  isExpanded: true,
                  hint: const Text('Or use a photo already uploaded'),
                  value: photos.any((p) => p.id == _values[field.id]) ? _values[field.id] : null,
                  items: [for (final p in photos) DropdownMenuItem(value: p.id, child: Text(p.name))],
                  onChanged: (v) => setState(() => _values[field.id] = v ?? ''),
                ),
              if (_values[field.id]?.isNotEmpty == true && !_uploading)
                const Padding(padding: EdgeInsets.only(top: 6), child: Tag('Photo attached')),
            ]),
          'date' => OutlinedButton.icon(
              icon: const Icon(Icons.event),
              label: Text(_values[field.id]?.isNotEmpty == true ? displayDate(_values[field.id]) : 'Choose date'),
              onPressed: () async {
                final now = DateTime.now();
                final picked = await showDatePicker(
                  context: context,
                  initialDate: DateTime.tryParse(_values[field.id] ?? '') ?? now,
                  firstDate: DateTime(now.year - 5),
                  lastDate: DateTime(now.year + 5),
                );
                if (picked != null) setState(() => _values[field.id] = isoDate(picked));
              },
            ),
          _ => TextField(
              controller: _text,
              autofocus: true,
              maxLength: 500,
              keyboardType: field.type == 'number' ? const TextInputType.numberWithOptions(decimal: true) : null,
              textInputAction: TextInputAction.next,
              onSubmitted: (_) => _next(),
              decoration: InputDecoration(
                hintText: 'Type or speak your answer',
                counterText: '',
                suffixIcon: VoiceButton(onTranscript: (t) {
                  _text.text = field.type == 'number' ? (RegExp(r'[\d.]+').firstMatch(t)?.group(0) ?? t) : t;
                }),
              ),
            ),
        },
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(_error!, style: const TextStyle(color: AppColors.error)),
          ),
        const SizedBox(height: 12),
        Row(children: [
          if (_step > 0)
            TextButton(onPressed: () { _syncText(); _goto(_step - 1); }, child: const Text('Back')),
          TextButton(
            onPressed: () => ref.read(assistantProvider.notifier).decline(widget.pending),
            child: const Text('Skip for now'),
          ),
          const Spacer(),
          FilledButton(
            onPressed: _uploading ? null : _next,
            child: Text(_step >= _fields.length - 1 ? 'Send answers' : 'Continue'),
          ),
        ]),
      ],
    );
  }
}

class _CardFrame extends StatelessWidget {
  const _CardFrame({required this.icon, required this.heading, required this.children, this.trailing});

  final IconData icon;
  final String heading;
  final Widget? trailing;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.symmetric(vertical: 8),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: context.isDark ? AppColors.darkCard : Colors.white,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: AppColors.primary, width: 1.4),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(icon, size: 16, color: AppColors.primaryDark),
            const SizedBox(width: 6),
            Expanded(
              child: Text(heading,
                  style: const TextStyle(
                      fontSize: 11, letterSpacing: 1, fontWeight: FontWeight.w700, color: AppColors.primaryDark)),
            ),
            if (trailing != null) trailing!,
          ]),
          const SizedBox(height: 8),
          ...children,
        ]),
      );
}
