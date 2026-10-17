import 'package:easy_localization/easy_localization.dart';
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
  'save_task': 'fos.assistant.approval_save_task',
  'record_expense': 'fos.assistant.approval_record_expense',
  'update_task': 'fos.assistant.approval_update_task',
  'delete_task': 'fos.assistant.approval_delete_task',
  'complete_task': 'fos.assistant.approval_complete_task',
  'record_ledger': 'fos.assistant.approval_record_ledger',
  'create_crop_case': 'fos.assistant.approval_create_crop_case',
  'record_crop_note': 'fos.assistant.approval_record_crop_note',
  'create_mission': 'fos.assistant.approval_create_mission',
  'record_service': 'fos.assistant.approval_record_service',
  'create_farm_group': 'fos.assistant.approval_create_farm_group',
  'create_shared_task': 'fos.assistant.approval_create_shared_task',
  'save_soil_report': 'fos.assistant.approval_save_soil_report',
};

const _fieldLabels = {
  'task_id': 'fos.assistant.field_task_id',
  'plot_id': 'fos.assistant.field_plot_id',
  'group_id': 'fos.assistant.field_group_id',
  'case_id': 'fos.assistant.field_case_id',
  'attachment_id': 'fos.assistant.field_attachment_id',
  'amount_inr': 'fos.assistant.field_amount_inr',
  'quote_inr': 'fos.assistant.field_quote_inr',
};

const _leading = ['title', 'description', 'amount_inr', 'due_date', 'occurred_on'];

/// Most identifying fields first, so the card reads like a sentence.
List<MapEntry<String, dynamic>> orderedArguments(Map<String, dynamic> args) => args.entries.toList()
  ..sort((a, b) {
    int rank(String k) => _leading.contains(k) ? _leading.indexOf(k) : _leading.length;
    return rank(a.key).compareTo(rank(b.key));
  });

String reviewValue(Object? v) {
  if (v == null || v == '') return 'fos.assistant.not_provided'.tr();
  if (v is String && RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(v)) return displayDate(v);
  if (v is bool) return v ? 'fos.assistant.yes'.tr() : 'fos.assistant.no'.tr();
  if (v is List) return v.take(36).map(reviewValue).join('\n');
  if (v is Map) {
    if (v['title'] != null) return '${v['title']}${v['done'] == true ? ' · ${'fos.assistant.completed'.tr()}' : ''}';
    if (v['property'] != null) {
      return '${'${v['property']}'.replaceAll('_', ' ')} · ${v['value']} ${v['unit_code'] ?? ''} '
          '(${v['reported_basis'] ?? ''}, ${'fos.assistant.depth_cm'.tr(namedArgs: {'top': '${v['depth_top_cm']}', 'bottom': '${v['depth_bottom_cm']}'})})';
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
      'delete_task' => 'fos.assistant.remove_task'.tr(),
      'update_task' => 'fos.assistant.save_changes'.tr(),
      'complete_task' => 'fos.assistant.mark_complete'.tr(),
      _ => 'fos.assistant.save_it'.tr(),
    };
    return _CardFrame(
      icon: Icons.fact_check_outlined,
      heading: 'fos.assistant.review_before_saving'.tr(),
      children: [
        Text((_approvalPrompts[pending.tool] ?? 'fos.assistant.approval_default').tr(),
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: ink)),
        const SizedBox(height: 10),
        for (final e in orderedArguments(pending.arguments))
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(_fieldLabels[e.key]?.tr() ?? e.key.replaceAll('_', ' '),
                  style: TextStyle(fontSize: 12, color: mutedColor(context))),
              Text(
                pending.reviewLabels[e.key] ??
                    (e.key == 'task_id'
                        ? tasks.where((t) => t.id == e.value).map((t) => t.title).firstOrNull ?? 'fos.assistant.selected_task'.tr()
                        : reviewValue(e.value)),
                style: TextStyle(fontSize: 14.5, color: ink),
              ),
            ]),
          ),
        Text('fos.assistant.saving_note'.tr(),
            style: TextStyle(fontSize: 11.5, color: mutedColor(context))),
        const SizedBox(height: 10),
        Row(children: [
          Expanded(
            child: OutlinedButton(onPressed: () => controller.decline(pending), child: Text('fos.assistant.dont_save'.tr())),
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
    if (v.isEmpty) return 'fos.assistant.add_detail'.tr();
    if (f.type == 'number' && num.tryParse(v) == null) return 'fos.assistant.enter_number'.tr();
    if (f.type == 'date' && DateTime.tryParse(v) == null) return 'fos.assistant.choose_date_error'.tr();
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
      heading: 'fos.assistant.mitra_needs_detail'.tr(),
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
                    label: Text('fos.assistant.take_photo_short'.tr())),
                OutlinedButton.icon(
                    onPressed: _uploading ? null : () => _photo(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: Text('fos.assistant.choose_photo_short'.tr())),
              ]),
              if (_uploading) const LinearProgressIndicator(),
              if (photos.isNotEmpty)
                DropdownButton<String>(
                  isExpanded: true,
                  hint: Text('fos.assistant.use_uploaded_photo'.tr()),
                  value: photos.any((p) => p.id == _values[field.id]) ? _values[field.id] : null,
                  items: [for (final p in photos) DropdownMenuItem(value: p.id, child: Text(p.name))],
                  onChanged: (v) => setState(() => _values[field.id] = v ?? ''),
                ),
              if (_values[field.id]?.isNotEmpty == true && !_uploading)
                Padding(padding: const EdgeInsets.only(top: 6), child: Tag('fos.assistant.photo_attached'.tr())),
            ]),
          'date' => OutlinedButton.icon(
              icon: const Icon(Icons.event),
              label: Text(_values[field.id]?.isNotEmpty == true ? displayDate(_values[field.id]) : 'fos.assistant.choose_date'.tr()),
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
                hintText: 'fos.assistant.type_or_speak'.tr(),
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
            TextButton(onPressed: () { _syncText(); _goto(_step - 1); }, child: Text('fos.assistant.back'.tr())),
          TextButton(
            onPressed: () => ref.read(assistantProvider.notifier).decline(widget.pending),
            child: Text('fos.assistant.skip_for_now'.tr()),
          ),
          const Spacer(),
          FilledButton(
            onPressed: _uploading ? null : _next,
            child: Text(_step >= _fields.length - 1 ? 'fos.assistant.send_answers'.tr() : 'fos.assistant.continue'.tr()),
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
            Icon(icon, size: 16, color: accentColor(context)),
            const SizedBox(width: 6),
            Expanded(
              child: Text(heading,
                  style: TextStyle(
                      fontSize: 11, letterSpacing: 1, fontWeight: FontWeight.w700, color: accentColor(context))),
            ),
            if (trailing != null) trailing!,
          ]),
          const SizedBox(height: 8),
          ...children,
        ]),
      );
}
