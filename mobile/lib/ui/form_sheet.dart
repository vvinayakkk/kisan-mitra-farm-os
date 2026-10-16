import 'package:flutter/material.dart';

import '../voice/voice_button.dart';
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
  String submit = 'Save',
  String? note,
}) =>
    showModalBottomSheet<Map<String, Object?>>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => _FormSheet(title: title, fields: fields, submit: submit, note: note),
    );

class _FormSheet extends StatefulWidget {
  const _FormSheet({required this.title, required this.fields, required this.submit, this.note});

  final String title;
  final List<FieldSpec> fields;
  final String submit;
  final String? note;

  @override
  State<_FormSheet> createState() => _FormSheetState();
}

class _FormSheetState extends State<_FormSheet> {
  late final _text = {
    for (final f in widget.fields)
      if (f.kind == FieldKind.text || f.kind == FieldKind.multiline || f.kind == FieldKind.number)
        f.key: TextEditingController(text: f.initial == null ? '' : '${f.initial}'),
  };
  late final _values = <String, Object?>{
    for (final f in widget.fields)
      if (!_text.containsKey(f.key)) f.key: f.initial ?? (f.kind == FieldKind.check ? false : null),
  };
  String? _error;

  @override
  void dispose() {
    for (final c in _text.values) {
      c.dispose();
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
          if (v == null) return setState(() => _error = '${f.label}: enter a number.');
        } else {
          v = raw.isEmpty ? null : raw;
        }
      } else {
        v = _values[f.key];
      }
      if (f.required && (v == null || v == '')) return setState(() => _error = '${f.label} is required.');
      out[f.key] = v;
    }
    Navigator.pop(context, out);
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(widget.title, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            for (final f in widget.fields) Padding(padding: const EdgeInsets.only(bottom: 10), child: _field(f)),
            if (widget.note != null)
              Text(widget.note!, style: TextStyle(fontSize: 12, color: mutedColor(context))),
            if (_error != null)
              Padding(padding: const EdgeInsets.only(top: 6), child: Text(_error!, style: const TextStyle(color: Colors.red))),
            const SizedBox(height: 8),
            Row(mainAxisAlignment: MainAxisAlignment.end, children: [
              TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
              FilledButton(onPressed: _submit, child: Text(widget.submit)),
            ]),
          ]),
        ),
      );

  Widget _field(FieldSpec f) {
    final label = '${f.label}${f.required ? ' *' : ''}';
    switch (f.kind) {
      case FieldKind.text:
      case FieldKind.multiline:
      case FieldKind.number:
        final c = _text[f.key]!;
        return TextField(
          controller: c,
          maxLength: f.maxLength,
          minLines: f.kind == FieldKind.multiline ? 2 : 1,
          maxLines: f.kind == FieldKind.multiline ? 5 : 1,
          keyboardType: f.kind == FieldKind.number ? const TextInputType.numberWithOptions(decimal: true) : null,
          decoration: InputDecoration(
            labelText: label,
            helperText: f.help,
            counterText: '',
            suffixIcon: f.kind == FieldKind.number
                ? null
                : VoiceButton(onTranscript: (t) => c.text = c.text.isEmpty ? t : '${c.text} $t'),
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
            if (picked != null) setState(() => _values[f.key] = isoDate(picked));
          },
        );
      case FieldKind.select:
        return DropdownButtonFormField<String>(
          initialValue: f.options.containsKey(_values[f.key]) ? _values[f.key] as String : null,
          isExpanded: true,
          decoration: InputDecoration(labelText: label, helperText: f.help),
          items: [for (final e in f.options.entries) DropdownMenuItem(value: e.key, child: Text(e.value))],
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
