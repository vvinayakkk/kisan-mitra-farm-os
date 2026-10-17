import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../voice/voice_button.dart';
import '../utils/constants.dart';
import 'kit.dart';

enum FieldKind { text, multiline, number, date, select, check }

class FieldSpec {
  const FieldSpec(
    this.key,
    this.label, {
    this.kind = FieldKind.text,
    this.options = const {},
    this.required = false,
    this.initial,
    this.maxLength,
    this.help,
  });

  final String key;
  final String label;
  final FieldKind kind;

  /// value → label, for [FieldKind.select].
  final Map<String, String> options;
  final bool required;
  final Object? initial;
  final int? maxLength;
  final String? help;
}

/// Bottom-sheet form returning `{key: value}` (numbers as num, dates as
/// yyyy-mm-dd, empty optional values as null) or null when cancelled.
Future<Map<String, Object?>?> showFormSheet(
  BuildContext context, {
  required String title,
  required List<FieldSpec> fields,
  String? submit,
  String? note,
}) =>
    showModalBottomSheet<Map<String, Object?>>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      isDismissible: false,
      enableDrag: false,
      showDragHandle: false,
      builder: (_) =>
          _FormSheet(title: title, fields: fields, submit: submit, note: note),
    );

class _FormSheet extends StatefulWidget {
  const _FormSheet(
      {required this.title,
      required this.fields,
      required this.submit,
      this.note});

  final String title;
  final List<FieldSpec> fields;
  final String? submit;
  final String? note;

  @override
  State<_FormSheet> createState() => _FormSheetState();
}

class _FormSheetState extends State<_FormSheet> {
  late final _text = {
    for (final f in widget.fields)
      if (f.kind == FieldKind.text ||
          f.kind == FieldKind.multiline ||
          f.kind == FieldKind.number)
        f.key: TextEditingController(
            text: f.initial == null ? '' : '${f.initial}'),
  };
  late final _values = <String, Object?>{
    for (final f in widget.fields)
      if (!_text.containsKey(f.key))
        f.key: f.initial ?? (f.kind == FieldKind.check ? false : null),
  };
  String? _error;
  String? _invalidField;
  bool _closing = false, _confirming = false;
  late final _focus = {for (final key in _text.keys) key: FocusNode()};
  late final _keys = {for (final f in widget.fields) f.key: GlobalKey()};
  bool get _dirty => widget.fields.any((f) => _text.containsKey(f.key)
      ? _text[f.key]!.text != (f.initial?.toString() ?? '')
      : _values[f.key] !=
          (f.initial ?? (f.kind == FieldKind.check ? false : null)));
  @override
  void initState() {
    super.initState();
    for (final c in _text.values) {
      c.addListener(_edited);
    }
  }

  void _edited() {
    if (mounted) setState(() {});
  }

  void _finish(Map<String, Object?>? result) {
    setState(() => _closing = true);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) Navigator.pop(context, result);
    });
  }

  Future<void> _cancel() async {
    if (_confirming) return;
    if (!_dirty) {
      _finish(null);
      return;
    }
    _confirming = true;
    final discard = await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
                title: const Text('Discard these changes?'),
                content: const Text('Your edits have not been saved yet.'),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(c, false),
                      child: const Text('Keep editing')),
                  TextButton(
                      onPressed: () => Navigator.pop(c, true),
                      child: const Text('Discard')),
                ]));
    _confirming = false;
    if (mounted && discard == true) _finish(null);
  }

  void _invalid(FieldSpec f, String message) {
    setState(() {
      _error = message;
      _invalidField = f.key;
    });
    _focus[f.key]?.requestFocus();
    final target = _keys[f.key]?.currentContext;
    if (target != null) {
      Scrollable.ensureVisible(target,
          duration: MediaQuery.disableAnimationsOf(context)
              ? Duration.zero
              : const Duration(milliseconds: 180));
    }
  }

  @override
  void dispose() {
    for (final c in _text.values) {
      c.dispose();
    }
    for (final node in _focus.values) {
      node.dispose();
    }
    super.dispose();
  }

  void _submit() {
    final out = <String, Object?>{};
    for (final f in widget.fields) {
      Object? v;
      if (_text.containsKey(f.key)) {
        final raw = _text[f.key]!.text.trim();
        if (f.kind == FieldKind.number && raw.isNotEmpty) {
          v = num.tryParse(raw);
          if (v == null || !(v as num).isFinite) {
            return _invalid(
                f,
                'fos.notebook.field_enter_number'
                    .tr(namedArgs: {'label': f.label}));
          }
        } else {
          v = raw.isEmpty ? null : raw;
        }
      } else {
        v = _values[f.key];
      }
      if (f.required && (v == null || v == '')) {
        return _invalid(
            f, 'fos.notebook.field_required'.tr(namedArgs: {'label': f.label}));
      }
      out[f.key] = v;
    }
    HapticFeedback.selectionClick();
    FocusManager.instance.primaryFocus?.unfocus();
    _finish(out);
  }

  @override
  Widget build(BuildContext context) => PopScope(
      canPop: _closing,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _cancel();
      },
      child: Padding(
        padding:
            EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: SingleChildScrollView(
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          padding: const EdgeInsets.all(16),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(widget.title,
                style: TextStyle(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                    color: inkColor(context))),
            const SizedBox(height: 8),
            for (final f in widget.fields)
              Padding(
                  key: _keys[f.key],
                  padding: const EdgeInsets.only(bottom: 10),
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _field(f),
                        if (_invalidField == f.key &&
                            (f.kind == FieldKind.date ||
                                f.kind == FieldKind.check))
                          Text(_error!,
                              style: const TextStyle(color: AppColors.error))
                      ])),
            if (widget.note != null)
              Text(widget.note!,
                  style: TextStyle(fontSize: 12, color: mutedColor(context))),
            const SizedBox(height: 8),
            Row(mainAxisAlignment: MainAxisAlignment.end, children: [
              TextButton(
                  onPressed: _cancel, child: Text('fos.notebook.cancel'.tr())),
              FilledButton(
                  onPressed: _submit,
                  child: Text(widget.submit ?? 'fos.notebook.save'.tr())),
            ]),
          ]),
        ),
      ));

  Widget _field(FieldSpec f) {
    final label = '${f.label}${f.required ? ' *' : ''}';
    switch (f.kind) {
      case FieldKind.text:
      case FieldKind.multiline:
      case FieldKind.number:
        final c = _text[f.key]!;
        return TextField(
          controller: c,
          focusNode: _focus[f.key],
          textCapitalization: f.kind == FieldKind.number
              ? TextCapitalization.none
              : TextCapitalization.sentences,
          textInputAction: f.kind == FieldKind.multiline
              ? TextInputAction.newline
              : f.key == widget.fields.last.key
                  ? TextInputAction.done
                  : TextInputAction.next,
          onSubmitted: (_) {
            if (f.key == widget.fields.last.key) {
              _submit();
              return;
            }
            final index = widget.fields.indexOf(f);
            final next = widget.fields
                .skip(index + 1)
                .where((f) => _focus.containsKey(f.key))
                .firstOrNull;
            if (next != null) {
              _focus[next.key]!.requestFocus();
            } else {
              FocusScope.of(context).nextFocus();
            }
          },
          onChanged: (_) {
            if (_invalidField == f.key) {
              setState(() {
                _error = null;
                _invalidField = null;
              });
            }
          },
          maxLength: f.maxLength,
          minLines: f.kind == FieldKind.multiline ? 2 : 1,
          maxLines: f.kind == FieldKind.multiline ? 5 : 1,
          keyboardType: f.kind == FieldKind.number
              ? const TextInputType.numberWithOptions(decimal: true)
              : null,
          decoration: InputDecoration(
            labelText: label,
            errorText: _invalidField == f.key ? _error : null,
            errorMaxLines: 3,
            helperText: f.help,
            counterText: '',
            suffixIcon: f.kind == FieldKind.number
                ? null
                : VoiceButton(
                    onTranscript: (t) =>
                        c.text = c.text.isEmpty ? t : '${c.text} $t'),
          ),
        );
      case FieldKind.date:
        final v = _values[f.key] as String?;
        return OutlinedButton.icon(
          icon: const Icon(Icons.event),
          label: Text(v == null ? label : '${f.label}: ${displayDate(v)}'),
          onPressed: () async {
            final picked = await showDatePicker(
              context: context,
              initialDate: DateTime.tryParse(v ?? '') ?? DateTime.now(),
              firstDate: DateTime(2000),
              lastDate: DateTime(2100),
            );
            if (picked != null) {
              setState(() => _values[f.key] = isoDate(picked));
            }
          },
        );
      case FieldKind.select:
        return DropdownButtonFormField<String>(
          initialValue: f.options.containsKey(_values[f.key])
              ? _values[f.key] as String
              : null,
          isExpanded: true,
          decoration: InputDecoration(
              labelText: label,
              helperText: f.help,
              errorText: _invalidField == f.key ? _error : null,
              errorMaxLines: 3),
          items: [
            for (final e in f.options.entries)
              DropdownMenuItem(value: e.key, child: Text(e.value))
          ],
          onChanged: (v) => setState(() => _values[f.key] = v),
        );
      case FieldKind.check:
        return CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          value: _values[f.key] == true,
          onChanged: (v) => setState(() => _values[f.key] = v ?? false),
          title: Text(f.label),
          subtitle: f.help == null ? null : Text(f.help!),
        );
    }
  }
}
