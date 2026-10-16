import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/api.dart';
import '../../ui/kit.dart';
import '../../utils/constants.dart';
import '../../voice/live_voice.dart';
import '../../voice/voice_button.dart';
import '../assistant_controller.dart';
import '../models.dart';

/// Text + voice + attachments. Disabled while a run is active or a card is
/// waiting, so only one question is answered at a time.
class Composer extends ConsumerStatefulWidget {
  const Composer({super.key, this.runContext = const RunContext(), this.controller});

  final RunContext runContext;
  final TextEditingController? controller;

  @override
  ConsumerState<Composer> createState() => ComposerState();
}

class ComposerState extends ConsumerState<Composer> {
  late final TextEditingController _text = widget.controller ?? TextEditingController();
  final _attached = <Attachment>[];
  bool _uploading = false;

  void setDraft(String text) {
    _text.text = text;
    _text.selection = TextSelection.collapsed(offset: text.length);
  }

  @override
  void dispose() {
    if (widget.controller == null) _text.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _text.text.trim();
    if (text.isEmpty && _attached.isEmpty) return;
    final ids = _attached.map((a) => a.id).toList();
    final names = _attached.map((a) => a.name).join(', ');
    _text.clear();
    setState(_attached.clear);
    await ref.read(assistantProvider.notifier).send(
          text.isEmpty ? 'Please look at the attached file.' : text,
          display: names.isEmpty ? null : '${text.isEmpty ? '' : '$text\n'}📎 $names',
          context: widget.runContext,
          attachmentIds: ids,
        );
  }

  Future<void> _attach() async {
    final choice = await showModalBottomSheet<String>(
      context: context,
      builder: (c) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(leading: const Icon(Icons.photo_camera_outlined), title: const Text('Take a photo'), onTap: () => Navigator.pop(c, 'camera')),
          ListTile(leading: const Icon(Icons.photo_library_outlined), title: const Text('Choose a photo'), onTap: () => Navigator.pop(c, 'gallery')),
          ListTile(
              leading: const Icon(Icons.attach_file),
              title: const Text('Choose a file'),
              subtitle: const Text('PDF, Word, Excel, CSV or text · up to 5 MB'),
              onTap: () => Navigator.pop(c, 'file')),
        ]),
      ),
    );
    if (choice == null) return;
    String? name;
    List<int>? bytes;
    if (choice == 'file') {
      final picked = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: const ['pdf', 'docx', 'xlsx', 'csv', 'txt', 'jpg', 'jpeg', 'png', 'webp'],
      );
      final file = picked.firstOrNull;
      name = file?.name;
      bytes = await file?.readAsBytes();
    } else {
      final image = await ImagePicker().pickImage(
          source: choice == 'camera' ? ImageSource.camera : ImageSource.gallery, maxWidth: 2048, imageQuality: 85);
      name = image?.name;
      bytes = await image?.readAsBytes();
    }
    if (name == null || bytes == null) return;
    setState(() => _uploading = true);
    try {
      final attachment = await ref.read(assistantProvider.notifier).uploadBytes(name, bytes);
      setState(() => _attached.add(attachment));
    } on ApiException catch (e) {
      if (mounted) showNotice(context, e.message);
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(assistantProvider);
    final locked = !state.ready || state.busy || state.pending != null;
    final dark = context.isDark;
    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.fromLTRB(8, 6, 8, 8),
        decoration: BoxDecoration(
          color: dark ? AppColors.darkSurface : Colors.white.withValues(alpha: 0.92),
          border: Border(top: BorderSide(color: dark ? Colors.white12 : Colors.black12)),
        ),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          if (_attached.isNotEmpty || _uploading)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Wrap(spacing: 6, children: [
                for (final a in _attached)
                  InputChip(
                    label: Text(a.name, overflow: TextOverflow.ellipsis),
                    avatar: Icon(a.isPhoto ? Icons.image_outlined : Icons.description_outlined, size: 16),
                    onDeleted: () => setState(() => _attached.remove(a)),
                  ),
                if (_uploading) const Chip(label: Text('Uploading…')),
              ]),
            ),
          if (state.pending != null && !state.busy)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text('Answer the card above to continue.',
                  style: TextStyle(fontSize: 12, color: mutedColor(context))),
            ),
          Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
            IconButton(
              tooltip: 'Attach a photo or file',
              onPressed: locked || _uploading ? null : _attach,
              icon: const Icon(Icons.add_circle_outline),
            ),
            Expanded(
              child: TextField(
                controller: _text,
                enabled: !locked,
                minLines: 1,
                maxLines: 5,
                maxLength: 6000,
                textInputAction: TextInputAction.newline,
                decoration: const InputDecoration(
                  hintText: 'Ask in any language…',
                  counterText: '',
                  contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                ),
              ),
            ),
            VoiceButton(
              enabled: !locked,
              onTranscript: (t) => setDraft(_text.text.isEmpty ? t : '${_text.text} $t'),
            ),
            if (state.busy)
              IconButton.filled(
                tooltip: 'Stop',
                style: IconButton.styleFrom(backgroundColor: AppColors.error),
                onPressed: state.running ? ref.read(assistantProvider.notifier).stop : null,
                icon: const Icon(Icons.stop_rounded),
              )
            else
              ValueListenableBuilder(
                valueListenable: _text,
                builder: (_, value, __) => value.text.trim().isEmpty && _attached.isEmpty
                    ? IconButton.filled(
                        tooltip: 'Live voice conversation',
                        onPressed: locked ? null : () => openLiveVoice(context, runContext: widget.runContext),
                        icon: const Icon(Icons.graphic_eq),
                      )
                    : IconButton.filled(
                        tooltip: 'Send',
                        onPressed: locked ? null : _send,
                        icon: const Icon(Icons.arrow_upward_rounded),
                      ),
              ),
          ]),
        ]),
      ),
    );
  }
}
