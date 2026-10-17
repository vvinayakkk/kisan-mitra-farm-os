import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/session.dart';
import '../../ui/form_sheet.dart';
import '../../ui/kit.dart';
import '../../ui/labels.dart';
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

  Map<String, String> get _ownership => {'owned': 'fos.notebook.owned'.tr(), 'leased': 'fos.notebook.leased'.tr(), 'shared': 'fos.notebook.shared'.tr()};
  Map<String, String> get _irrigation => {
        'rainfed': 'fos.notebook.rainfed'.tr(), 'drip': 'fos.notebook.drip'.tr(), 'sprinkler': 'fos.notebook.sprinkler'.tr(), 'flood': 'fos.notebook.flood'.tr(), 'manual': 'fos.notebook.manual'.tr(), 'other': 'fos.notebook.other'.tr(),
      };
  Map<String, String> get _cycleStatus => {for (final k in const ['planned', 'growing', 'harvested', 'failed']) k: statusLabel(k)};

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
    final v = await showFormSheet(context, title: f == null ? 'fos.notebook.add_farm'.tr() : 'fos.notebook.edit_farm'.tr(), fields: [
      FieldSpec('name', 'fos.notebook.farm_name'.tr(), required: true, initial: f?['name'], maxLength: 120),
      FieldSpec('region_id', 'fos.notebook.state_region'.tr(), kind: FieldKind.select, required: true, initial: f?['region_id'], options: regions),
      FieldSpec('ownership_type', 'fos.notebook.ownership'.tr(), kind: FieldKind.select, required: true, initial: f?['ownership_type'] ?? 'owned', options: _ownership),
      FieldSpec('irrigation_method', 'fos.notebook.irrigation'.tr(), kind: FieldKind.select, required: true, initial: f?['irrigation_method'] ?? 'rainfed', options: _irrigation),
      FieldSpec('water_source', 'fos.notebook.water_source'.tr(), initial: f?['water_source'], maxLength: 160),
    ]);
    if (v == null || !mounted) return;
    await notebookWrite(context, ref, (api) async {
      f == null ? await api.post('/api/farms', body: v) : await api.put('/api/farms/${f['id']}', body: v);
    }, done: 'fos.notebook.farm_saved'.tr(), reload: _loader);
  }

  Future<void> _plot(_FieldsData d, [Map<String, dynamic>? p]) async {
    final farms = {for (final f in d.farms) str(f['id']): str(f['name'])};
    final v = await showFormSheet(context,
        title: p == null ? 'fos.notebook.add_field'.tr() : 'fos.notebook.edit_field'.tr(),
        note: 'fos.notebook.coords_note'.tr(),
        fields: [
          FieldSpec('farm_id', 'fos.notebook.farm'.tr(), kind: FieldKind.select, required: true, initial: p?['farm_id'] ?? farms.keys.firstOrNull, options: farms),
          FieldSpec('name', 'fos.notebook.field_name'.tr(), initial: p?['name'], maxLength: 120),
          FieldSpec('area_ha', 'fos.notebook.area_ha_label'.tr(), kind: FieldKind.number, required: true, initial: p?['area_ha']),
          FieldSpec('latitude', 'fos.notebook.latitude'.tr(), kind: FieldKind.number, required: true, initial: p?['latitude']),
          FieldSpec('longitude', 'fos.notebook.longitude'.tr(), kind: FieldKind.number, required: true, initial: p?['longitude']),
          FieldSpec('soil_texture', 'fos.notebook.soil_texture'.tr(), initial: p?['soil_texture'], maxLength: 60),
        ]);
    if (v == null || !mounted) return;
    final body = {...v, 'name': v['name'] ?? '', 'boundary_geojson': p?['boundary_geojson']};
    await notebookWrite(context, ref, (api) async {
      p == null ? await api.post('/api/plots', body: body) : await api.put('/api/plots/${p['id']}', body: body);
    }, done: 'fos.notebook.field_saved'.tr(), reload: _loader);
  }

  Future<void> _cycle(_FieldsData d, [Map<String, dynamic>? c]) async {
    final plots = {for (final p in d.plots) str(p['id']): str(p['name'], 'fos.notebook.field'.tr())};
    final crops = {for (final c in asMaps(d.options['crops'])) str(c['id']): cropName(c['name'])};
    final v = await showFormSheet(context,
        title: c == null ? 'fos.notebook.add_season'.tr() : 'fos.notebook.edit_season'.tr(),
        note: 'fos.notebook.harvested_note'.tr(),
        fields: [
          FieldSpec('plot_id', 'fos.notebook.field'.tr(), kind: FieldKind.select, required: true, initial: c?['plot_id'], options: plots),
          FieldSpec('crop_id', 'fos.notebook.crop'.tr(), kind: FieldKind.select, required: true, initial: c?['crop_id'], options: crops),
          FieldSpec('season', 'fos.notebook.season'.tr(), required: true, initial: c?['season'], maxLength: 40, help: 'fos.notebook.season_hint'.tr()),
          FieldSpec('sowing_date', 'fos.notebook.sowing_date'.tr(), kind: FieldKind.date, required: true, initial: c?['sowing_date']),
          FieldSpec('expected_harvest_date', 'fos.notebook.expected_harvest'.tr(), kind: FieldKind.date, initial: c?['expected_harvest_date']),
          FieldSpec('actual_harvest_date', 'fos.notebook.actual_harvest'.tr(), kind: FieldKind.date, initial: c?['actual_harvest_date']),
          FieldSpec('status', 'fos.notebook.status'.tr(), kind: FieldKind.select, required: true, initial: c?['status'] ?? 'planned', options: _cycleStatus),
        ]);
    if (v == null || !mounted) return;
    final body = {...v, 'variety_id': c?['variety_id']};
    await notebookWrite(context, ref, (api) async {
      c == null ? await api.post('/api/crop-cycles', body: body) : await api.put('/api/crop-cycles/${c['id']}', body: body);
    }, done: 'fos.notebook.season_saved'.tr(), reload: _loader);
  }

  Future<void> _weather(Map<String, dynamic> farm, List<Map<String, dynamic>> plots, bool linked) async {
    if (linked) {
      await notebookWrite(context, ref, (api) => api.delete('/api/farms/${farm['id']}/weather-link'),
          done: 'fos.notebook.weather_stopped'.tr(), reload: _loader);
      return;
    }
    final v = await showFormSheet(context, title: 'fos.notebook.get_forecasts_for'.tr(namedArgs: {'farm': '${farm['name']}'}), fields: [
      FieldSpec('plot_id', 'fos.notebook.field_for_forecast'.tr(), kind: FieldKind.select, required: true,
          options: {for (final p in plots) str(p['id']): str(p['name'], 'fos.notebook.field'.tr())}),
      FieldSpec('consent', 'fos.notebook.share_grid_consent'.tr(), kind: FieldKind.check),
    ]);
    if (v == null || !mounted) return;
    if (v['consent'] != true) return showNotice(context, 'fos.notebook.consent_forecasts'.tr());
    await notebookWrite(context, ref,
        (api) => api.post('/api/farms/${farm['id']}/weather-link', body: {'plot_id': v['plot_id'], 'consent_to_share_coarse_grid': true}),
        done: 'fos.notebook.weather_enabled'.tr(), reload: _loader);
  }

  @override
  Widget build(BuildContext context) => Loader<_FieldsData>(
        key: _loader,
        loading: 'fos.notebook.loading'.tr(),
        load: _load,
        builder: (context, d) => ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
          SectionTitle('fos.notebook.farms'.tr(), trailing: FilledButton.tonalIcon(onPressed: () => _farm(d), icon: const Icon(Icons.add), label: Text('fos.notebook.btn_farm'.tr()))),
          if (d.farms.isEmpty) EmptyView(title: 'fos.notebook.no_farms'.tr()),
          for (final f in d.farms) ...[
            Card(
              child: ListTile(
                title: Text(str(f['name'])),
                subtitle: Text('${[_ownership[f['ownership_type']], _irrigation[f['irrigation_method']]].whereType<String>().join(' · ')}'
                    '${str(f['water_source']).isEmpty ? '' : ' · ${phrase(f['water_source'])}'}'),
                onTap: () => _farm(d, f),
                trailing: PopupMenuButton<String>(
                  onSelected: (v) => _weather(f, d.plots.where((p) => p['farm_id'] == f['id']).toList(), v == 'unlink'),
                  itemBuilder: (_) => [
                    PopupMenuItem(value: 'link', child: Text('fos.notebook.use_for_forecasts'.tr())),
                    PopupMenuItem(value: 'unlink', child: Text('fos.notebook.stop_weather'.tr())),
                  ],
                ),
              ),
            ),
          ],
          SectionTitle('fos.notebook.fields'.tr(),
              trailing: FilledButton.tonalIcon(onPressed: d.farms.isEmpty ? null : () => _plot(d), icon: const Icon(Icons.add), label: Text('fos.notebook.btn_field'.tr()))),
          for (final p in d.plots)
            Card(
              child: ListTile(
                title: Text(str(p['name'], 'fos.notebook.field'.tr())),
                subtitle: Text('fos.notebook.area_ha_value'.tr(namedArgs: {'area': qty(p['area_ha']), 'soil': str(p['soil_texture'], 'fos.notebook.soil_not_recorded'.tr())})),
                onTap: () => _plot(d, p),
              ),
            ),
          SectionTitle('fos.notebook.crop_seasons'.tr(),
              trailing: FilledButton.tonalIcon(onPressed: d.plots.isEmpty ? null : () => _cycle(d), icon: const Icon(Icons.add), label: Text('fos.notebook.btn_season'.tr()))),
          if (d.cycles.isEmpty) EmptyView(title: 'fos.notebook.no_seasons'.tr()),
          for (final c in d.cycles)
            Card(
              child: ListTile(
                title: Text('${cropName(str(c['crop_name'], 'fos.notebook.crop'.tr()))} · ${str(c['season']).toLowerCase() == 'demo current' ? 'Current season' : str(c['season'])}'),
                subtitle: Text('${statusLabel(c['status'])} · ${'fos.notebook.sown'.tr(namedArgs: {'date': displayDate(str(c['sowing_date']))})}'
                    '${c['expected_harvest_date'] != null ? ' · ${'fos.notebook.harvest_est'.tr(namedArgs: {'date': displayDate(str(c['expected_harvest_date']))})}' : ''}'),
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
