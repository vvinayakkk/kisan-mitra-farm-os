import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../assistant/assistant_controller.dart';
import '../assistant/helper_sheet.dart';
import '../core/api.dart';
import '../ui/kit.dart';
import '../ui/loader.dart';
import '../utils/constants.dart';
import 'saathi.dart';
import 'workspace_tools.dart';

/// Photo assessment. The result is a model's reading of the photo, not a lab
/// diagnosis, and it may say it cannot tell.
class CropDoctorScreen extends ConsumerStatefulWidget {
  const CropDoctorScreen({super.key});

  @override
  ConsumerState<CropDoctorScreen> createState() => _CropDoctorScreenState();
}

class _CropDoctorScreenState extends ConsumerState<CropDoctorScreen> {
  Uint8List? _image;
  String? _fileId;
  String _phase = 'idle'; // idle | uploading | checking
  Map<String, dynamic>? _diagnostic;
  String? _error;

  Future<void> _pick(ImageSource source) async {
    final picked = await ImagePicker().pickImage(source: source, maxWidth: 2048, imageQuality: 88);
    if (picked == null) return;
    final bytes = await picked.readAsBytes();
    setState(() {
      _image = bytes;
      _diagnostic = null;
      _error = null;
      _phase = 'uploading';
      _fileId = null;
    });
    try {
      final attachment = await ref.read(assistantProvider.notifier).uploadBytes(picked.name, bytes);
      setState(() => _fileId = attachment.id);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _phase = 'idle');
    }
  }

  Future<void> _check() async {
    setState(() {
      _phase = 'checking';
      _error = null;
    });
    try {
      final result = await ref.read(workspaceToolsProvider).inspect('diagnose_crop', {'file_id': _fileId});
      setState(() => _diagnostic = asMap(result['diagnostic']));
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'fos.farm.check_failed'.tr());
    } finally {
      if (mounted) setState(() => _phase = 'idle');
    }
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    final d = _diagnostic;
    final confidence = (d?['confidence'] as num?)?.toDouble() ?? 0;
    return Scaffold(
      appBar: AppBar(title: Text('fos.farm.crop_doctor'.tr())),
      floatingActionButton: const HelperButton(contextKey: 'crops'),
      body: FarmBackground(
        child: ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 96), children: [
          const PreparedBySaathi(area: 'crops'),
          FarmCard(
            child: Column(children: [
              if (_image != null)
                ClipRRect(
                  borderRadius: BorderRadius.circular(12),
                  child: Image.memory(_image!, height: 220, width: double.infinity, fit: BoxFit.cover, semanticLabel: 'fos.farm.selected_crop_photo'.tr()),
                )
              else
                EmptyView(icon: Icons.local_florist_outlined, title: 'fos.farm.photograph_leaf'.tr()),
              const SizedBox(height: 10),
              Wrap(spacing: 8, runSpacing: 8, alignment: WrapAlignment.center, children: [
                FilledButton.tonalIcon(
                  onPressed: _phase != 'idle' ? null : () => _pick(ImageSource.camera),
                  icon: const Icon(Icons.photo_camera_outlined),
                  label: Text('fos.farm.take_photo'.tr()),
                ),
                FilledButton.tonalIcon(
                  onPressed: _phase != 'idle' ? null : () => _pick(ImageSource.gallery),
                  icon: const Icon(Icons.photo_library_outlined),
                  label: Text('fos.farm.choose_photo'.tr()),
                ),
                FilledButton.icon(
                  onPressed: _fileId == null || _phase != 'idle'
                      ? null
                      : () {
                          HapticFeedback.selectionClick();
                          _check();
                        },
                  icon: const Icon(Icons.health_and_safety_outlined),
                  label: Text(_phase == 'checking' ? 'fos.farm.checking'.tr() : _phase == 'uploading' ? 'fos.farm.uploading'.tr() : 'fos.farm.check_crop'.tr()),
                ),
              ]),
              if (_phase != 'idle')
                Padding(
                  padding: const EdgeInsets.only(top: 10),
                  child: LoadingView(_phase == 'uploading'
                      ? 'fos.farm.uploading'.tr()
                      : 'fos.farm.checking_minute'.tr()),
                ),
            ]),
          ),
          if (_error != null) ErrorView(_error!, onRetry: _fileId == null ? null : _check),
          if (d != null && d.isNotEmpty) ...[
            const SizedBox(height: 12),
            FarmCard(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(str(d['crop_identified'], 'fos.farm.crop_not_identified'.tr()).toUpperCase(),
                    style: TextStyle(fontSize: 11, letterSpacing: 1, color: context.isDark ? AppColors.primaryLight : AppColors.primaryDark, fontWeight: FontWeight.w700)),
                const SizedBox(height: 4),
                Text(str(d['disease_name'], 'fos.farm.unclear_photo'.tr()),
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: ink)),
                const SizedBox(height: 4),
                Text(str(d['description']), style: TextStyle(color: ink)),
                const SizedBox(height: 8),
                Tag('fos.farm.confidence_note'.tr(namedArgs: {'value': '${confidence.round()}'}),
                    color: confidence >= 70 ? AppColors.primaryDark : AppColors.warning),
                if (confidence > 0) ...[
                  if ((d['symptoms'] as List?)?.isNotEmpty == true) ...[
                    SectionTitle('fos.farm.what_visible'.tr()),
                    for (final s in d['symptoms'] as List) Text('• $s', style: TextStyle(color: ink)),
                  ],
                  if ((d['solutions'] as List?)?.isNotEmpty == true) ...[
                    SectionTitle('fos.farm.what_could_do'.tr()),
                    for (final s in asMaps(d['solutions']))
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        title: Text(str(s['title']), style: TextStyle(color: ink)),
                        subtitle: Text([str(s['details']), if (str(s['stage']).isNotEmpty) 'fos.farm.stage'.tr(namedArgs: {'value': '${s['stage']}'})].join('\n'), style: TextStyle(color: mutedColor(context))),
                      ),
                  ],
                ],
                const SizedBox(height: 6),
                FilledButton.tonalIcon(
                  onPressed: () {
                    HapticFeedback.selectionClick();
                    ref.read(assistantProvider.notifier).send(
                          'Help me open a crop follow-up from this photo assessment: '
                          '${str(d['disease_name'])} on ${str(d['crop_identified'])}, confidence ${confidence.round()}%. '
                          'Ask what I observed and when, and show it for review before saving.',
                          context: const RunContext(view: 'crops'),
                        );
                    showHelperSheet(context, 'crops');
                  },
                  icon: const Icon(Icons.playlist_add),
                  label: Text('fos.farm.follow_up_mitra'.tr()),
                ),
              ]),
            ),
          ],
        ]),
      ),
    );
  }
}
