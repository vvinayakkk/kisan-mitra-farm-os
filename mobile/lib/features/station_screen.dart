import '../tour/app_tour.dart';
import 'dart:async';

import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../assistant/helper_sheet.dart';
import '../core/api.dart';
import 'package:go_router/go_router.dart';
import '../core/session.dart';
import '../ui/kit.dart';
import 'saathi.dart';
import '../ui/labels.dart';
import '../ui/loader.dart';
import '../ui/provenance.dart';
import '../utils/constants.dart';

/// Latest enrolled-station snapshot. Demo stations are labelled as simulated;
/// a reading's age is always shown so stale values are not read as current.
class StationScreen extends ConsumerStatefulWidget {
  const StationScreen({super.key});

  @override
  ConsumerState<StationScreen> createState() => _StationScreenState();
}

class _StationScreenState extends ConsumerState<StationScreen> {
  Map<String, dynamic>? _snapshot;
  String? _error;
  Timer? _timer;
  String? _station;
  bool _loading = false;

  static const _readings = <(String, String, String, IconData)>[
    ('temperature', 'fos.farm.air_temperature', '°C', Icons.thermostat),
    ('humidity', 'fos.farm.humidity', '%', Icons.water_drop_outlined),
    ('soilMoisture', 'fos.farm.soil_moisture', '%', Icons.grass),
    (
      'soilTemperature',
      'fos.farm.soil_temperature',
      '°C',
      Icons.landscape_outlined
    ),
    ('rainfall', 'fos.farm.rainfall', 'mm', Icons.umbrella_outlined),
    ('windSpeed', 'fos.farm.wind_speed', 'km/h', Icons.air),
    ('airQualityPM25', 'fos.farm.pm25', 'µg/m³', Icons.blur_on),
    ('uvIndex', 'fos.farm.uv_index', '', Icons.wb_sunny_outlined),
  ];

  static const _moreReadings = <(String, String, String, IconData)>[
    ('pressure', 'fos.farm.pressure', 'hPa', Icons.speed),
    ('lightIntensity', 'fos.farm.light', 'lux', Icons.light_mode_outlined),
    ('batteryVoltage', 'fos.farm.battery', 'V', Icons.battery_std),
  ];

  @override
  void initState() {
    super.initState();
    _load();
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => _load());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    if (_loading) return;
    _loading = true;
    try {
      final api = ref.read(apiProvider);
      if (_station == null) {
        final stations =
            asMaps(asMap(await api.get('/api/sensors/stations'))['stations']);
        if (stations.isEmpty) {
          if (mounted) setState(() => _snapshot = {'available': false});
          return;
        }
        _station = str(stations.first['station_id']);
      }
      final data =
          asMap(await api.get('/api/assistant/station/$_station', fresh: true));
      if (mounted) {
        setState(() {
          _snapshot = data;
          _error = null;
        });
      }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      _loading = false;
    }
  }

  String _age(Map<String, dynamic> provenance) {
    final seconds = (provenance['observation_age_seconds'] as num?)?.toInt();
    if (seconds == null) return 'fos.farm.time_unknown'.tr();
    if (seconds < 90) {
      return 'fos.farm.read_seconds_ago'.tr(namedArgs: {'count': '$seconds'});
    }
    if (seconds < 5400) {
      return 'fos.farm.read_minutes_ago'
          .tr(namedArgs: {'count': '${(seconds / 60).round()}'});
    }
    return 'fos.farm.read_hours_ago'
        .tr(namedArgs: {'count': '${(seconds / 3600).round()}'});
  }

  /// General-guide verdicts (icon, text, colour) from simple bands; not crop-specific advice.
  List<(IconData, String, Color)> _verdicts(Map<String, dynamic> data) {
    num? n(String k) => data[k] is num ? data[k] as num : null;
    final out = <(IconData, String, Color)>[];
    final soil = n('soilMoisture');
    if (soil != null) {
      out.add(soil < 20
          ? (Icons.grass, 'fos.farm2.st_soil_dry'.tr(), AppColors.warning)
          : soil > 40
              ? (Icons.grass, 'fos.farm2.st_soil_wet'.tr(), AppColors.info)
              : (
                  Icons.grass,
                  'fos.farm2.st_soil_ok'.tr(),
                  AppColors.primaryDark
                ));
    }
    final t = n('temperature');
    if (t != null && t >= 35) {
      out.add(
          (Icons.thermostat, 'fos.farm2.st_very_hot'.tr(), AppColors.warning));
    }
    final h = n('humidity');
    if (h != null && h >= 85) {
      out.add((
        Icons.water_drop_outlined,
        'fos.farm2.st_very_humid'.tr(),
        AppColors.info
      ));
    }
    final w = n('windSpeed');
    if (w != null && w >= 30) {
      out.add((Icons.air, 'fos.farm2.st_strong_wind'.tr(), AppColors.warning));
    }
    final r = n('rainfall');
    if (r != null && r > 0) {
      out.add((
        Icons.umbrella_outlined,
        'fos.farm2.st_rained'.tr(),
        AppColors.info
      ));
    }
    return out.take(4).toList();
  }

  Widget _grid(BuildContext context, Map<String, dynamic> data,
      List<(String, String, String, IconData)> defs) {
    final ink = inkColor(context);
    return LayoutBuilder(builder: (context, c) {
      final columns = c.maxWidth > 520 ? 3 : 2;
      final items = [
        for (final (key, label, unit, icon) in defs)
          if (data[key] is num)
            (
              label.tr(),
              '${(data[key] as num).toStringAsFixed(1)} $unit'.trim(),
              icon
            ),
      ];
      return GridView.count(
        crossAxisCount: columns,
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        mainAxisSpacing: 8,
        crossAxisSpacing: 8,
        mainAxisExtent: 160 * MediaQuery.textScalerOf(context).scale(1),
        children: [
          for (final (label, value, icon) in items)
            FarmCard(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(icon,
                        size: 18,
                        color: context.isDark
                            ? AppColors.primaryLight
                            : AppColors.primaryDark),
                    const SizedBox(height: 4),
                    Text(value,
                        style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                            color: ink)),
                    Text(label,
                        style: TextStyle(
                            fontSize: 13, color: mutedColor(context))),
                  ]),
            ),
        ],
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    final s = _snapshot;
    final data = asMap(s?['data']);
    final provenance = asMap(s?['provenance']);
    final verdicts = _verdicts(data);
    final flags = (data['quality_flags'] as List? ?? const [])
        .map((e) => '$e')
        .where((f) => f != 'synthetic')
        .toList();
    return Scaffold(
      appBar: AppBar(actions: const [TourReplayButton()], title: Text('fos.farm.farm_station'.tr())),
      floatingActionButton: const HelperButton(contextKey: 'station'),
      body: FarmBackground(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
              padding: const EdgeInsets.fromLTRB(24, 8, 24, 96),
              children: [
                const PreparedBySaathi(area: 'today'),
              const TourAnchor(id: 'station', child: FeatureIntro(
                    eyebrow: 'FARM STATION',
                    title: 'A pulse on your field.',
                    detail:
                        'Actual readings from your connected station, with the time they were received.',
                    icon: Icons.sensors_outlined)),

                if (_error != null) ErrorView(_error!, onRetry: _load),
                if (s == null && _error == null)
                  LoadingView('fos.farm.loading'.tr()),
                if (s != null && s['available'] != true)
                  EmptyView(
                    icon: Icons.sensors_off_outlined,
                    title: 'Your field, connected',
                    detail:
                        'Connect a physical station for soil and air readings. Nearby weather works without a station.',
                    action: FilledButton.tonal(
                        onPressed: () => context.push('/weather'),
                        child: const Text('See nearby weather')),
                  ),
                if (s != null && s['available'] == true) ...[
                  FarmCard(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(children: [
                            Expanded(
                              child: Text(phrase(s['source']),
                                  style: TextStyle(
                                      fontWeight: FontWeight.w700,
                                      fontSize: 16,
                                      color: ink)),
                            ),
                            ProvenanceBadge(provenance),
                          ]),
                          const SizedBox(height: 4),
                          Text(
                              '${str(s['station_id']).startsWith('DEMO-') ? 'Field station' : str(s['station_id'])} · ${_age(provenance)}',
                              style: TextStyle(color: mutedColor(context))),
                          if (flags.isNotEmpty)
                            Padding(
                              padding: const EdgeInsets.only(top: 6),
                              child: Wrap(spacing: 6, children: [
                                for (final f in flags)
                                  if (f != 'synthetic')
                                    Tag(flagLabel(f), color: AppColors.warning),
                              ]),
                            ),
                        ]),
                  ),
                  const SizedBox(height: 10),
                  SectionTitle('fos.farm2.st_means'.tr(),
                      trailing: Text('fos.farm2.st_general_guide'.tr(),
                          style: TextStyle(
                              fontSize: 12, color: mutedColor(context)))),
                  FarmCard(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (verdicts.isEmpty)
                            Text('fos.farm2.st_nothing'.tr(),
                                style: TextStyle(
                                    fontSize: 16,
                                    fontWeight: FontWeight.w600,
                                    color: ink))
                          else
                            for (final (icon, text, color) in verdicts)
                              Padding(
                                padding:
                                    const EdgeInsets.symmetric(vertical: 5),
                                child: Row(children: [
                                  Icon(icon,
                                      size: 26,
                                      color: context.isDark
                                          ? Color.lerp(color, Colors.white, 0.4)
                                          : color),
                                  const SizedBox(width: 12),
                                  Expanded(
                                      child: Text(text,
                                          style: TextStyle(
                                              fontSize: 18,
                                              fontWeight: FontWeight.w700,
                                              color: ink))),
                                ]),
                              ),
                        ]),
                  ),
                  const SizedBox(height: 10),
                  _grid(context, data, _readings),
                  if (_moreReadings.any((r) => data[r.$1] is num))
                    ExpansionTile(
                      tilePadding: EdgeInsets.zero,
                      shape: const Border(),
                      title: Text('fos.farm2.st_more'.tr(),
                          style: TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                              color: ink)),
                      children: [_grid(context, data, _moreReadings)],
                    ),
                ],
              ]),
        ),
      ),
    );
  }
}
