import 'dart:async';

import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../assistant/helper_sheet.dart';
import '../core/api.dart';
import '../core/config.dart';
import '../core/session.dart';
import '../ui/kit.dart';
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

  static const _readings = <(String, String, String, IconData)>[
    ('temperature', 'fos.farm.air_temperature', '°C', Icons.thermostat),
    ('humidity', 'fos.farm.humidity', '%', Icons.water_drop_outlined),
    ('soilMoisture', 'fos.farm.soil_moisture', '% relative', Icons.grass),
    ('soilTemperature', 'fos.farm.soil_temperature', '°C', Icons.landscape_outlined),
    ('rainfall', 'fos.farm.rainfall', 'mm', Icons.umbrella_outlined),
    ('windSpeed', 'fos.farm.wind_speed', 'km/h', Icons.air),
    ('pressure', 'fos.farm.pressure', 'hPa', Icons.speed),
    ('airQualityPM25', 'fos.farm.pm25', 'µg/m³', Icons.blur_on),
    ('uvIndex', 'fos.farm.uv_index', '', Icons.wb_sunny_outlined),
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
    try {
      final data = asMap(await ref.read(apiProvider).get('/api/assistant/station/${AppConfig.stationId}'));
      if (mounted) {
      setState(() {
        _snapshot = data;
        _error = null;
      });
    }
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  String _age(Map<String, dynamic> provenance) {
    final seconds = (provenance['observation_age_seconds'] as num?)?.toInt();
    if (seconds == null) return 'fos.farm.time_unknown'.tr();
    if (seconds < 90) return 'fos.farm.read_seconds_ago'.tr(namedArgs: {'count': '$seconds'});
    if (seconds < 5400) return 'fos.farm.read_minutes_ago'.tr(namedArgs: {'count': '${(seconds / 60).round()}'});
    return 'fos.farm.read_hours_ago'.tr(namedArgs: {'count': '${(seconds / 3600).round()}'});
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    final s = _snapshot;
    final data = asMap(s?['data']);
    final provenance = asMap(s?['provenance']);
    final flags = (data['quality_flags'] as List? ?? const []).map((e) => '$e').toList();
    return Scaffold(
      appBar: AppBar(title: Text('fos.farm.farm_station'.tr())),
      floatingActionButton: const HelperButton(contextKey: 'station'),
      body: FarmBackground(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 96), children: [
            if (_error != null) ErrorView(_error!, onRetry: _load),
            if (s == null && _error == null) LoadingView('fos.farm.loading'.tr()),
            if (s != null && s['available'] != true)
              EmptyView(
                icon: Icons.sensors_off_outlined,
                title: 'fos.farm.no_station_readings'.tr(),
              ),
            if (s != null && s['available'] == true) ...[
              FarmCard(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(children: [
                    Expanded(
                      child: Text(str(s['source']),
                          style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16, color: ink)),
                    ),
                    ProvenanceBadge(provenance),
                  ]),
                  const SizedBox(height: 4),
                  Text('${str(data['station_id'], str(s['station_id']))} · ${_age(provenance)}',
                      style: TextStyle(color: mutedColor(context))),
                  if (flags.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Wrap(spacing: 6, children: [
                        for (final f in flags) Tag(f.replaceAll('_', ' '), color: AppColors.warning),
                      ]),
                    ),
                  if (provenance['origin'] == 'synthetic')
                    Padding(
                      padding: const EdgeInsets.only(top: 6),
                      child: Text('fos.farm.simulated_readings'.tr(),
                          style: TextStyle(fontSize: 12, color: mutedColor(context))),
                    ),
                ]),
              ),
              const SizedBox(height: 10),
              LayoutBuilder(builder: (context, c) {
                final columns = c.maxWidth > 520 ? 3 : 2;
                final items = [
                  for (final (key, label, unit, icon) in _readings)
                    if (data[key] is num) (label.tr(), '${(data[key] as num).toStringAsFixed(1)} $unit'.trim(), icon),
                ];
                return GridView.count(
                  crossAxisCount: columns,
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  mainAxisSpacing: 8,
                  crossAxisSpacing: 8,
                  childAspectRatio: 1.7,
                  children: [
                    for (final (label, value, icon) in items)
                      FarmCard(
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                          Icon(icon, size: 18, color: context.isDark ? AppColors.primaryLight : AppColors.primaryDark),
                          const SizedBox(height: 4),
                          Text(value, style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: ink)),
                          Text(label, style: TextStyle(fontSize: 12, color: mutedColor(context))),
                        ]),
                      ),
                  ],
                );
              }),
            ],
          ]),
        ),
      ),
    );
  }
}
