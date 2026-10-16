import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../assistant/chat_screen.dart';
import '../core/api.dart';
import '../core/config.dart';
import '../core/language.dart';
import '../core/session.dart';
import '../core/workspace_cache.dart';
import '../services/theme_service.dart';
import '../ui/form_sheet.dart';
import '../ui/kit.dart';
import '../ui/loader.dart';
import '../ui/provenance.dart';

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
    final v = await showFormSheet(context, title: 'Edit profile', fields: [
      FieldSpec('name', 'Name', required: true, initial: p['name'], maxLength: 100),
      FieldSpec('location', 'Village / location', initial: p['location'], maxLength: 200),
      FieldSpec('district', 'District', initial: p['district'], maxLength: 100),
      FieldSpec('preferred_language', 'Preferred language', kind: FieldKind.select,
          initial: normalizeLanguage(str(p['preferred_language'])) ?? ref.read(languageProvider).code,
          options: {for (final (code, name) in kAppLanguages) code: name}),
      FieldSpec('crops', 'Crops (comma separated)', initial: joined(p['crops'])),
      FieldSpec('excess_resources', 'Resources you can share', initial: joined(p['excess_resources'])),
      FieldSpec('required_resources', 'Resources you need', initial: joined(p['required_resources'])),
    ]);
    if (v == null || !mounted) return;
    List<String> split(Object? s) => '${s ?? ''}'.split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
    try {
      await ref.read(apiProvider).post('/api/profile/save', body: {
        'name': v['name'],
        'location': v['location'] ?? '',
        'district': v['district'] ?? '',
        'preferred_language': v['preferred_language'],
        'crops': split(v['crops']),
        'excess_resources': split(v['excess_resources']),
        'required_resources': split(v['required_resources']),
      });
      ref.read(workspaceCacheProvider).invalidate();
      if (v['preferred_language'] != null) await ref.read(languageProvider.notifier).choose('${v['preferred_language']}');
      if (mounted) showNotice(context, 'Your profile has been saved.');
    } on ApiException catch (e) {
      if (mounted) showNotice(context, e.message);
    }
    _loader.currentState?.reload();
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    final auth = ref.watch(authProvider);
    return Scaffold(
      appBar: AppBar(title: Text('My farm profile', style: TextStyle(color: ink)), foregroundColor: ink),
      body: FarmBackground(
        child: Loader<Map<String, dynamic>>(
          key: _loader,
          loading: 'Opening your farm profile…',
          load: () async => asMap(asMap(await ref.read(apiProvider).get('/api/profile'))['profile']),
          builder: (context, p) {
            String list(Object? v, String empty) => v is List && v.isNotEmpty ? v.join(', ') : empty;
            return ListView(padding: const EdgeInsets.all(12), children: [
              if (p.isEmpty)
                const EmptyView(title: 'No farmer profile is available for this account.', detail: 'Your identity has not been inferred.')
              else
                FarmCard(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      Expanded(child: Text(str(p['name'], 'Not provided'), style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: ink))),
                      ProvenanceBadge(asMap(p['provenance']).isEmpty ? {'origin': p['data_origin']} : asMap(p['provenance'])),
                    ]),
                    Text('${str(p['location'], 'Location not set')} · ${str(p['district'], 'District not set')}',
                        style: TextStyle(color: mutedColor(context))),
                    const Divider(),
                    _row(context, 'Reported land area', p['land_size_acres'] is num ? '${(p['land_size_acres'] as num).toStringAsFixed(2)} acres' : 'Not provided'),
                    _row(context, 'Area in saved fields',
                        p['mapped_plot_area_acres'] is num ? '${(p['mapped_plot_area_acres'] as num).toStringAsFixed(2)} acres' : 'No fields saved'),
                    _row(context, 'Crops', list(p['crops'], 'None added')),
                    _row(context, 'Can share', list(p['excess_resources'], 'None added')),
                    _row(context, 'Needs', list(p['required_resources'], 'None added')),
                    Text('Saved field areas are separate from your reported total.', style: TextStyle(fontSize: 11.5, color: mutedColor(context))),
                    Align(alignment: Alignment.centerRight, child: FilledButton.tonal(onPressed: () => _edit(p), child: const Text('Edit profile'))),
                  ]),
                ),
              const SizedBox(height: 12),
              FarmCard(
                padding: EdgeInsets.zero,
                child: Column(children: [
                  ListTile(
                    leading: const Icon(Icons.agriculture_outlined),
                    title: const Text('My fields and crop seasons'),
                    onTap: () => context.push('/notebook?tab=fields'),
                  ),
                  ListTile(
                    leading: const Icon(Icons.spa_outlined),
                    title: const Text('Saathi follow-ups'),
                    onTap: () => context.push('/saathi'),
                  ),
                  ListTile(
                    leading: const Icon(Icons.translate),
                    title: const Text('Language'),
                    subtitle: Text(kAppLanguages.firstWhere((l) => l.$1 == ref.watch(languageProvider).code).$2),
                    onTap: () => showLanguagePicker(context),
                  ),
                  SwitchListTile(
                    secondary: const Icon(Icons.dark_mode_outlined),
                    title: const Text('Dark theme'),
                    value: ref.watch(themeProvider) == ThemeMode.dark,
                    onChanged: (_) => ref.read(themeProvider.notifier).toggle(),
                  ),
                  ListTile(
                    leading: const Icon(Icons.dns_outlined),
                    title: const Text('Server'),
                    subtitle: Text('${AppConfig.apiBaseUrl} · ${auth.mode == BackendMode.demo ? 'demo data' : auth.mode == BackendMode.live ? 'live accounts' : 'mode unknown'}'),
                  ),
                  ListTile(
                    leading: const Icon(Icons.logout),
                    title: const Text('Sign out'),
                    subtitle: const Text('Ends this device’s session. Your farm records stay on the server.'),
                    onTap: () async {
                      if (await confirmAction(context, title: 'Sign out?', body: 'You will need to sign in again on this phone.', confirm: 'Sign out', cancel: 'Stay')) {
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
          SizedBox(width: 140, child: Text(label, style: TextStyle(color: mutedColor(context)))),
          Expanded(child: Text(value, style: TextStyle(color: inkColor(context)))),
        ]),
      );
}
