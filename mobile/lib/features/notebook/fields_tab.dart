import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/session.dart';
import '../../ui/form_sheet.dart';
import '../../ui/kit.dart';
import '../../ui/loader.dart';
import 'records_tabs.dart';

/// Farms, plots and crop seasons the farmer saved. Coordinates and areas are
/// what the farmer entered; a future harvest date is their estimate.
class FieldsTab extends ConsumerStatefulWidget {
  const FieldsTab({super.key});

  @override
  ConsumerState<FieldsTab> createState() => _FieldsTabState();
}

class _FieldsTabState extends ConsumerState<FieldsTab> {
  final _loader = GlobalKey<LoaderState<_FieldsData>>();

  static const _ownership = {'owned': 'Owned', 'leased': 'Leased', 'shared': 'Shared'};
  static const _irrigation = {
    'rainfed': 'Rainfed', 'drip': 'Drip', 'sprinkler': 'Sprinkler', 'flood': 'Flood', 'manual': 'Manual', 'other': 'Other',
  };
  static const _cycleStatus = {'planned': 'Planned', 'growing': 'Growing', 'harvested': 'Harvested', 'failed': 'Failed'};

  Future<_FieldsData> _load() async {
    final api = ref.read(apiProvider);
    final r = await Future.wait([
      api.get('/api/farms'),
      api.get('/api/plots'),
      api.get('/api/crop-cycles'),
      api.get('/api/onboarding/options'),
    ]);
    return _FieldsData(
      farms: asMaps(asMap(r[0])['farms']),
      plots: asMaps(asMap(r[1])['plots']),
      cycles: asMaps(asMap(r[2])['crop_cycles']),
      options: asMap(r[3]),
    );
  }

  Future<void> _farm(_FieldsData d, [Map<String, dynamic>? f]) async {
    final regions = {for (final r in asMaps(d.options['regions'])) str(r['id']): str(r['name'])};
    final v = await showFormSheet(context, title: f == null ? 'Add a farm' : 'Edit farm', fields: [
      FieldSpec('name', 'Farm name', required: true, initial: f?['name'], maxLength: 120),
      FieldSpec('region_id', 'State / region', kind: FieldKind.select, required: true, initial: f?['region_id'], options: regions),
      FieldSpec('ownership_type', 'Ownership', kind: FieldKind.select, required: true, initial: f?['ownership_type'] ?? 'owned', options: _ownership),
      FieldSpec('irrigation_method', 'Irrigation', kind: FieldKind.select, required: true, initial: f?['irrigation_method'] ?? 'rainfed', options: _irrigation),
      FieldSpec('water_source', 'Water source', initial: f?['water_source'], maxLength: 160),
    ]);
    if (v == null || !mounted) return;
    await notebookWrite(context, ref, (api) async {
      f == null ? await api.post('/api/farms', body: v) : await api.put('/api/farms/${f['id']}', body: v);
    }, done: 'Farm saved.', reload: _loader);
  }

  Future<void> _plot(_FieldsData d, [Map<String, dynamic>? p]) async {
    final farms = {for (final f in d.farms) str(f['id']): str(f['name'])};
    final v = await showFormSheet(context,
        title: p == null ? 'Add a field' : 'Edit field',
        note: 'Coordinates set the forecast grid location.',
        fields: [
          FieldSpec('farm_id', 'Farm', kind: FieldKind.select, required: true, initial: p?['farm_id'] ?? farms.keys.firstOrNull, options: farms),
          FieldSpec('name', 'Field name', initial: p?['name'], maxLength: 120),
          FieldSpec('area_ha', 'Area (hectares)', kind: FieldKind.number, required: true, initial: p?['area_ha']),
          FieldSpec('latitude', 'Latitude', kind: FieldKind.number, required: true, initial: p?['latitude']),
          FieldSpec('longitude', 'Longitude', kind: FieldKind.number, required: true, initial: p?['longitude']),
          FieldSpec('soil_texture', 'Soil texture', initial: p?['soil_texture'], maxLength: 60),
        ]);
    if (v == null || !mounted) return;
    final body = {...v, 'name': v['name'] ?? '', 'boundary_geojson': p?['boundary_geojson']};
    await notebookWrite(context, ref, (api) async {
      p == null ? await api.post('/api/plots', body: body) : await api.put('/api/plots/${p['id']}', body: body);
    }, done: 'Field saved.', reload: _loader);
  }

  Future<void> _cycle(_FieldsData d, [Map<String, dynamic>? c]) async {
    final plots = {for (final p in d.plots) str(p['id']): str(p['name'], 'Field')};
    final crops = {for (final c in asMaps(d.options['crops'])) str(c['id']): str(c['name'])};
    final v = await showFormSheet(context,
        title: c == null ? 'Add a crop season' : 'Edit crop season',
        note: 'Harvested needs a past harvest date.',
        fields: [
          FieldSpec('plot_id', 'Field', kind: FieldKind.select, required: true, initial: c?['plot_id'], options: plots),
          FieldSpec('crop_id', 'Crop', kind: FieldKind.select, required: true, initial: c?['crop_id'], options: crops),
          FieldSpec('season', 'Season', required: true, initial: c?['season'], maxLength: 40, help: 'e.g. Kharif 2026'),
          FieldSpec('sowing_date', 'Sowing date', kind: FieldKind.date, required: true, initial: c?['sowing_date']),
          FieldSpec('expected_harvest_date', 'Expected harvest (your estimate)', kind: FieldKind.date, initial: c?['expected_harvest_date']),
          FieldSpec('actual_harvest_date', 'Actual harvest', kind: FieldKind.date, initial: c?['actual_harvest_date']),
          FieldSpec('status', 'Status', kind: FieldKind.select, required: true, initial: c?['status'] ?? 'planned', options: _cycleStatus),
        ]);
    if (v == null || !mounted) return;
    final body = {...v, 'variety_id': c?['variety_id']};
    await notebookWrite(context, ref, (api) async {
      c == null ? await api.post('/api/crop-cycles', body: body) : await api.put('/api/crop-cycles/${c['id']}', body: body);
    }, done: 'Crop season saved.', reload: _loader);
  }

  Future<void> _weather(Map<String, dynamic> farm, List<Map<String, dynamic>> plots, bool linked) async {
    if (linked) {
      await notebookWrite(context, ref, (api) => api.delete('/api/farms/${farm['id']}/weather-link'),
          done: 'Weather sharing stopped.', reload: _loader);
      return;
    }
    final v = await showFormSheet(context, title: 'Get forecasts for ${farm['name']}', fields: [
      FieldSpec('plot_id', 'Field to locate the forecast', kind: FieldKind.select, required: true,
          options: {for (final p in plots) str(p['id']): str(p['name'], 'Field')}),
      const FieldSpec('consent', 'Share this field’s coarse grid location with the weather source', kind: FieldKind.check),
    ]);
    if (v == null || !mounted) return;
    if (v['consent'] != true) return showNotice(context, 'Consent needed for forecasts.');
    await notebookWrite(context, ref,
        (api) => api.post('/api/farms/${farm['id']}/weather-link', body: {'plot_id': v['plot_id'], 'consent_to_share_coarse_grid': true}),
        done: 'Weather sharing enabled.', reload: _loader);
  }

  @override
  Widget build(BuildContext context) => Loader<_FieldsData>(
        key: _loader,
        loading: 'Loading…',
        load: _load,
        builder: (context, d) => ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
          SectionTitle('Farms', trailing: FilledButton.tonalIcon(onPressed: () => _farm(d), icon: const Icon(Icons.add), label: const Text('Farm'))),
          if (d.farms.isEmpty) const EmptyView(title: 'No farms yet.'),
          for (final f in d.farms) ...[
            Card(
              child: ListTile(
                title: Text(str(f['name'])),
                subtitle: Text('${_ownership[f['ownership_type']] ?? ''} · ${_irrigation[f['irrigation_method']] ?? ''}'
                    '${str(f['water_source']).isEmpty ? '' : ' · ${f['water_source']}'}'),
                onTap: () => _farm(d, f),
                trailing: PopupMenuButton<String>(
                  onSelected: (v) => _weather(f, d.plots.where((p) => p['farm_id'] == f['id']).toList(), v == 'unlink'),
                  itemBuilder: (_) => const [
                    PopupMenuItem(value: 'link', child: Text('Use field for forecasts')),
                    PopupMenuItem(value: 'unlink', child: Text('Stop weather sharing')),
                  ],
                ),
              ),
            ),
          ],
          SectionTitle('Fields',
              trailing: FilledButton.tonalIcon(onPressed: d.farms.isEmpty ? null : () => _plot(d), icon: const Icon(Icons.add), label: const Text('Field'))),
          for (final p in d.plots)
            Card(
              child: ListTile(
                title: Text(str(p['name'], 'Field')),
                subtitle: Text('${p['area_ha']} ha · ${str(p['soil_texture'], 'Soil not recorded')}'),
                onTap: () => _plot(d, p),
              ),
            ),
          SectionTitle('Crop seasons',
              trailing: FilledButton.tonalIcon(onPressed: d.plots.isEmpty ? null : () => _cycle(d), icon: const Icon(Icons.add), label: const Text('Season'))),
          if (d.cycles.isEmpty) const EmptyView(title: 'No crop seasons.'),
          for (final c in d.cycles)
            Card(
              child: ListTile(
                title: Text('${str(c['crop_name'], 'Crop')} · ${str(c['season'])}'),
                subtitle: Text('${_cycleStatus[c['status']] ?? str(c['status'])} · sown ${displayDate(str(c['sowing_date']))}'
                    '${c['expected_harvest_date'] != null ? ' · harvest (est.) ${displayDate(str(c['expected_harvest_date']))}' : ''}'),
                onTap: () => _cycle(d, c),
              ),
            ),
        ]),
      );
}

class _FieldsData {
  const _FieldsData({required this.farms, required this.plots, required this.cycles, required this.options});

  final List<Map<String, dynamic>> farms;
  final List<Map<String, dynamic>> plots;
  final List<Map<String, dynamic>> cycles;
  final Map<String, dynamic> options;
}
