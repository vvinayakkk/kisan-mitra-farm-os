import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../assistant/chat_screen.dart';
import '../core/api.dart';
import '../core/language.dart';
import '../core/session.dart';
import '../core/workspace_cache.dart';
import '../services/theme_service.dart';
import '../ui/form_sheet.dart';
import '../ui/kit.dart';
import '../ui/labels.dart';
import '../ui/loader.dart';
import '../ui/provenance.dart';
import '../ui/mitra_orb.dart';

/// The farmer record the server resolved for this session. Identity is never
/// inferred client-side.
class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  final _loader = GlobalKey<LoaderState<Map<String, dynamic>>>();

  Future<void> _edit(Map<String, dynamic> p) async {
    String joined(Object? v) => v is List ? v.join(', ') : str(v);
    final v = await showFormSheet(context,
        title: 'fos.market.edit_profile'.tr(),
        fields: [
          FieldSpec('name', 'fos.market.name'.tr(),
              required: true, initial: p['name'], maxLength: 100),
          FieldSpec('location', 'fos.market.village'.tr(),
              initial: p['location'], maxLength: 200),
          FieldSpec('land_size_acres', 'Land area in acres',
              kind: FieldKind.number, initial: p['land_size_acres']),
          FieldSpec('district', 'fos.market.district'.tr(),
              initial: p['district'], maxLength: 100),
          FieldSpec('preferred_language', 'fos.market.preferred_language'.tr(),
              kind: FieldKind.select,
              initial: normalizeLanguage(str(p['preferred_language'])) ??
                  ref.read(languageProvider).code,
              options: {for (final (code, name) in kAppLanguages) code: name}),
          FieldSpec('crops', 'fos.market.crops_csv'.tr(),
              initial: joined(p['crops'])),
          FieldSpec('excess_resources', 'fos.market.can_share_long'.tr(),
              initial: joined(p['excess_resources'])),
          FieldSpec('required_resources', 'fos.market.need_long'.tr(),
              initial: joined(p['required_resources'])),
        ]);
    if (v == null || !mounted) return;
    List<String> split(Object? s) => '${s ?? ''}'
        .split(',')
        .map((e) => e.trim())
        .where((e) => e.isNotEmpty)
        .toList();
    try {
      await ref.read(apiProvider).post('/api/profile/save', body: {
        'name': v['name'],
        'location': v['location'] ?? '',
        'district': v['district'] ?? '',
        if (v['land_size_acres'] != null)
          'land_size_acres': v['land_size_acres'],
        'preferred_language': v['preferred_language'],
        'crops': split(v['crops']),
        'excess_resources': split(v['excess_resources']),
        'required_resources': split(v['required_resources']),
      });
      ref.read(workspaceCacheProvider).invalidate();
      if (v['preferred_language'] != null) {
        await ref
            .read(languageProvider.notifier)
            .choose('${v['preferred_language']}');
      }
      if (mounted) showNotice(context, 'fos.market.profile_saved'.tr());
    } on ApiException catch (e) {
      if (mounted) showNotice(context, e.message);
    }
    _loader.currentState?.reload();
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    return Scaffold(
      appBar: AppBar(title: Text('fos.market.my_profile'.tr())),
      body: FarmBackground(
        child: Loader<Map<String, dynamic>>(
          key: _loader,
          loading: 'fos.market.loading'.tr(),
          load: () async => asMap(asMap(
              await ref.read(apiProvider).get('/api/profile'))['profile']),
          builder: (context, p) {
            String list(Object? v, String empty, {bool crops = false}) =>
                v is List && v.isNotEmpty
                    ? v.map((e) => crops ? cropName(e) : phrase(e)).join(', ')
                    : empty;
            final complete = [
              str(p['name']).isNotEmpty,
              str(p['state']).isNotEmpty,
              (p['crops'] is List && (p['crops'] as List).isNotEmpty),
              p['land_size_acres'] != null,
              p['latitude'] != null
            ].where((v) => v).length;
            return ListView(padding: const EdgeInsets.all(24), children: [
              const Center(child: MitraOrb(size: 100, active: false)),
              const SizedBox(height: 12),
              Text('Your story. Your land.',
                  style: TextStyle(
                      fontSize: 27, fontWeight: FontWeight.w600, color: ink)),
              const SizedBox(height: 6),
              Text('A little more about you makes Mitra a lot more helpful.',
                  style: TextStyle(color: mutedColor(context), height: 1.5)),
              const SizedBox(height: 20),
              FarmCard(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    Row(children: [
                      const Expanded(child: Text('Your farm profile')),
                      Text('${complete * 20}%')
                    ]),
                    const SizedBox(height: 12),
                    LinearProgressIndicator(
                        value: complete / 5,
                        minHeight: 5,
                        borderRadius: BorderRadius.circular(8)),
                    TextButton(
                        onPressed: () => context.push('/onboarding'),
                        child: Text(complete < 5
                            ? 'Continue setting up'
                            : 'Review my farm details')),
                  ])),
              const SizedBox(height: 16),
              if (p.isEmpty)
                EmptyView(title: 'fos.market.no_profile'.tr())
              else
                FarmCard(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(children: [
                          Expanded(
                              child: Text(
                                  str(p['name'],
                                      'fos.market.not_provided'.tr()),
                                  style: TextStyle(
                                      fontSize: 20,
                                      fontWeight: FontWeight.w700,
                                      color: ink))),
                          ProvenanceBadge(asMap(p['provenance']).isEmpty
                              ? {'origin': p['data_origin']}
                              : asMap(p['provenance'])),
                        ]),
                        Text(
                            '${phrase(str(p['location'], 'fos.market.location_not_set'.tr()))} · ${phrase(str(p['district'], 'fos.market.district_not_set'.tr()))}',
                            style: TextStyle(
                                fontSize: 14, color: mutedColor(context))),
                        const Divider(),
                        _row(
                            context,
                            'fos.market.land_area'.tr(),
                            p['land_size_acres'] is num
                                ? 'fos.market.acres'.tr(namedArgs: {
                                    'n': (p['land_size_acres'] as num)
                                        .toStringAsFixed(2)
                                  })
                                : 'fos.market.not_provided'.tr()),
                        _row(
                            context,
                            'fos.market.saved_area'.tr(),
                            p['mapped_plot_area_acres'] is num
                                ? 'fos.market.acres'.tr(namedArgs: {
                                    'n': (p['mapped_plot_area_acres'] as num)
                                        .toStringAsFixed(2)
                                  })
                                : 'fos.market.no_fields'.tr()),
                        _row(
                            context,
                            'fos.market.crops'.tr(),
                            list(p['crops'], 'fos.market.none_added'.tr(),
                                crops: true)),
                        _row(
                            context,
                            'fos.market.can_share'.tr(),
                            list(p['excess_resources'],
                                'fos.market.none_added'.tr())),
                        _row(
                            context,
                            'fos.market.needs'.tr(),
                            list(p['required_resources'],
                                'fos.market.none_added'.tr())),
                        Align(
                            alignment: Alignment.centerRight,
                            child: FilledButton.tonal(
                                onPressed: () {
                                  HapticFeedback.selectionClick();
                                  _edit(p);
                                },
                                child: Text('fos.market.edit'.tr()))),
                      ]),
                ),
              const SizedBox(height: 12),
              FarmCard(
                padding: EdgeInsets.zero,
                child: Column(children: [
                  ListTile(
                    leading: const Icon(Icons.agriculture_outlined),
                    title: Text('fos.market.my_fields'.tr()),
                    onTap: () => context.push('/notebook?tab=fields'),
                  ),
                  ListTile(
                    leading: const Icon(Icons.spa_outlined),
                    title: Text('fos.market.saathi_followups'.tr()),
                    onTap: () => context.push('/saathi'),
                  ),
                  ListTile(
                    leading: const Icon(Icons.translate),
                    title: Text('fos.market.language'.tr()),
                    subtitle: Text(kAppLanguages
                        .firstWhere(
                            (l) => l.$1 == ref.watch(languageProvider).code)
                        .$2),
                    onTap: () => showLanguagePicker(context),
                  ),
                  SwitchListTile(
                    secondary: const Icon(Icons.dark_mode_outlined),
                    title: Text('fos.market.dark_theme'.tr()),
                    value: ref.watch(themeProvider) == ThemeMode.dark,
                    onChanged: (_) => ref.read(themeProvider.notifier).toggle(),
                  ),
                  ListTile(
                    leading: const Icon(Icons.logout),
                    title: Text('fos.market.sign_out'.tr()),
                    onTap: () async {
                      if (await confirmAction(context,
                          title: 'fos.market.sign_out_q'.tr(),
                          body: 'fos.market.sign_out_body'.tr(),
                          confirm: 'fos.market.sign_out'.tr(),
                          cancel: 'fos.market.stay'.tr())) {
                        await ref.read(authProvider.notifier).signOut();
                      }
                    },
                  ),
                ]),
              ),
            ]);
          },
        ),
      ),
    );
  }

  Widget _row(BuildContext context, String label, String value) => Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(
              width: 140,
              child: Text(label,
                  style: TextStyle(fontSize: 14, color: mutedColor(context)))),
          Expanded(
              child: Text(value,
                  style: TextStyle(fontSize: 14, color: inkColor(context)))),
        ]),
      );
}
