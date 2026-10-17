import 'package:easy_localization/easy_localization.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/api.dart';
import '../../ui/kit.dart';
import '../../utils/constants.dart';
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
          text.isEmpty ? 'fos.assistant.look_at_file'.tr() : text,
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
          ListTile(leading: const Icon(Icons.photo_camera_outlined), title: Text('fos.assistant.take_photo'.tr()), onTap: () => Navigator.pop(c, 'camera')),
          ListTile(leading: const Icon(Icons.photo_library_outlined), title: Text('fos.assistant.choose_photo'.tr()), onTap: () => Navigator.pop(c, 'gallery')),
          ListTile(
              leading: const Icon(Icons.attach_file),
              title: Text('fos.assistant.choose_file'.tr()),
              subtitle: Text('fos.assistant.file_types_hint'.tr()),
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
    // Original input bar: one rounded glass pill floating over the gradient.
    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 4, 12, 10),
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
                if (_uploading) Chip(label: Text('fos.assistant.uploading'.tr())),
              ]),
            ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
            decoration: BoxDecoration(
              color: dark ? Colors.white.withValues(alpha: 0.08) : Colors.white.withValues(alpha: 0.92),
              borderRadius: BorderRadius.circular(28),
              border: Border.all(
                color: dark ? Colors.white.withValues(alpha: 0.14) : AppColors.primary.withValues(alpha: 0.25),
              ),
              boxShadow: [BoxShadow(color: AppColors.primary.withValues(alpha: 0.08), blurRadius: 12, offset: const Offset(0, 4))],
            ),
            child: Row(children: [
              IconButton(
                tooltip: 'fos.assistant.attach_tooltip'.tr(),
                onPressed: locked || _uploading ? null : _attach,
                icon: Icon(Icons.add_rounded, color: mutedColor(context)),
              ),
              Expanded(
                child: TextField(
                  controller: _text,
                  enabled: !locked,
                  minLines: 1,
                  maxLines: 5,
                  maxLength: 6000,
                  textInputAction: TextInputAction.newline,
                  decoration: InputDecoration(
                    hintText: state.pending != null && !state.busy
                        ? 'fos.assistant.answer_card_hint'.tr()
                        : 'fos.assistant.ask_any_language'.tr(),
                    counterText: '',
                    filled: false,
                    border: InputBorder.none,
                    enabledBorder: InputBorder.none,
                    focusedBorder: InputBorder.none,
                    disabledBorder: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(vertical: 12),
                  ),
                ),
              ),
              VoiceButton(
                enabled: !locked,
                onTranscript: (t) => setDraft(_text.text.isEmpty ? t : '${_text.text} $t'),
              ),
              Padding(
                padding: const EdgeInsets.only(right: 2),
                child: state.busy
                    ? IconButton.filled(
                        tooltip: 'fos.assistant.stop'.tr(),
                        style: IconButton.styleFrom(backgroundColor: AppColors.error),
                        onPressed: state.running ? ref.read(assistantProvider.notifier).stop : null,
                        icon: const Icon(Icons.stop_rounded),
                      )
                    : IconButton.filled(
                        tooltip: 'fos.assistant.send'.tr(),
                        style: IconButton.styleFrom(backgroundColor: AppColors.primary, foregroundColor: Colors.white),
                        onPressed: locked
                            ? null
                            : () {
                                HapticFeedback.lightImpact();
                                _send();
                              },
                        icon: const Icon(Icons.arrow_upward_rounded),
                      ),
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}
