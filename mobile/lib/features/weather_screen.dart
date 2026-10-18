import '../tour/app_tour.dart';
import 'dart:async';

import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:geolocator/geolocator.dart';

import '../assistant/assistant_controller.dart';
import '../assistant/helper_sheet.dart';
import '../core/session.dart';
import '../ui/kit.dart';
import '../ui/loader.dart';
import '../ui/provenance.dart';
import '../utils/constants.dart';

String weatherLabel(num? code) {
  if (code == null) return 'fos.farm.forecast'.tr();
  if (code >= 95) return 'fos.farm.w_thunderstorms'.tr();
  if (code >= 85 && code <= 89) return 'fos.farm.w_snow_showers'.tr();
  if (code >= 71 && code <= 79) return 'fos.farm.w_snow'.tr();
  if (code >= 61) return 'fos.farm.w_rain'.tr();
  if (code >= 51) return 'fos.farm.w_drizzle'.tr();
  if (code >= 45) return 'fos.farm.w_fog'.tr();
  if (code >= 1) return 'fos.farm.w_cloudy'.tr();
  return 'fos.farm.w_clear'.tr();
}

IconData weatherIcon(num? code) {
  if (code == null) return Icons.cloud_outlined;
  if (code >= 95) return Icons.thunderstorm_outlined;
  if ((code >= 71 && code <= 77) || code == 85 || code == 86) {
    return Icons.ac_unit;
  }
  if (code >= 51) return Icons.umbrella_outlined;
  if (code >= 45) return Icons.foggy;
  if (code >= 1) return Icons.cloud_outlined;
  return Icons.wb_sunny_outlined;
}

String aqiBand(num v) => v <= 50
    ? 'fos.farm.aqi_good'.tr()
    : v <= 100
        ? 'fos.farm.aqi_moderate'.tr()
        : v <= 150
            ? 'fos.farm.aqi_sensitive'.tr()
            : v <= 200
                ? 'fos.farm.aqi_unhealthy'.tr()
                : v <= 300
                    ? 'fos.farm.aqi_very_unhealthy'.tr()
                    : 'fos.farm.aqi_hazardous'.tr();

/// Regional model forecasts for the farm or a chosen city. Always labelled as
/// model estimates, never as field measurements.
class WeatherScreen extends ConsumerStatefulWidget {
  const WeatherScreen({super.key});

  @override
  ConsumerState<WeatherScreen> createState() => _WeatherScreenState();
}

class _WeatherScreenState extends ConsumerState<WeatherScreen> {
  Map<String, dynamic>? _city;
  bool _nearby = false;
  final _loader = GlobalKey<LoaderState<Map<String, dynamic>>>();

  Future<Map<String, dynamic>> _load() async {
    final api = ref.read(apiProvider);
    final city = _city;
    if (city != null) {
      return asMap(await api
          .get('/api/weather/city-dashboard', query: {'city_id': city['id']}));
    }
    try {
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.whileInUse || permission == LocationPermission.always) {
        final position = await Geolocator.getCurrentPosition(
            locationSettings: const LocationSettings(
                accuracy: LocationAccuracy.low, timeLimit: Duration(seconds: 8)));
        final data = asMap(await api.get('/api/weather/location-dashboard', query: {
          'latitude': position.latitude.toStringAsFixed(2),
          'longitude': position.longitude.toStringAsFixed(2),
        }));
        _nearby = true;
        return data;
      }
    } catch (_) { /* Saved farm weather is still usable without device GPS. */ }
    final data = asMap(await api.get('/api/weather/dashboard'));
    return data;
  }

  Future<void> _useLocation() async {
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (!mounted) return;
    if (permission == LocationPermission.denied ||
        permission == LocationPermission.deniedForever) {
      showNotice(
          context, 'Location is optional. You can choose a city instead.');
      return;
    }
    setState(() {
      _nearby = true;
      _city = null;
    });
    _loader.currentState?.reload();
  }

  Future<void> _pickCity() async {
    final picked = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => const _CitySearch(),
    );
    if (picked == null) return;
    setState(() => _city = picked);
    _loader.currentState?.reload();
  }

  String? get _cityName => _city == null
      ? null
      : [_city!['name'], _city!['admin1'], _city!['country']]
          .where((e) => e != null && '$e'.isNotEmpty)
          .join(', ');

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_nearby && _city == null
            ? 'Weather near you'
            : _city == null
                ? 'fos.farm.farm_weather'.tr()
                : 'fos.farm.city_weather'.tr()),
        actions: [
          const TourReplayButton(),
          TourAnchor(id: 'nearby', child: IconButton(
              tooltip: 'Weather near me',
              icon: const Icon(Icons.my_location),
              onPressed: _useLocation)),
          TourAnchor(id: 'city', child: IconButton(
              tooltip: 'fos.farm.choose_city'.tr(),
              icon: const Icon(Icons.location_city),
              onPressed: _pickCity)),
          if (_city != null)
            IconButton(
              tooltip: 'fos.farm.back_to_farm'.tr(),
              icon: const Icon(Icons.agriculture),
              onPressed: () {
                setState(() => _city = null);
                _loader.currentState?.reload();
              },
            ),
        ],
      ),
      floatingActionButton: HelperButton(
        contextKey: 'weather',
        runContext: RunContext(view: 'weather', weatherCity: _cityName),
      ),
      body: FarmBackground(
        child: RefreshIndicator(
          onRefresh: () async => _loader.currentState?.reload(),
          child: Loader<Map<String, dynamic>>(
            key: _loader,
            loading: 'fos.farm.loading'.tr(),
            load: _load,
            builder: (context, d) => _WeatherBody(data: d, cityName: _cityName),
          ),
        ),
      ),
    );
  }
}

class _WeatherBody extends StatelessWidget {
  const _WeatherBody({required this.data, this.cityName});

  final Map<String, dynamic> data;
  final String? cityName;

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    if (data['requires_farm_selection'] == true) {
      return ListView(
          children: [EmptyView(title: 'fos.farm.select_farm_first'.tr())]);
    }
    if (data['available'] != true) {
      return ListView(children: [
        EmptyView(
          icon: Icons.cloud_off_outlined,
          title: 'fos.farm.no_weather'.tr(),
          detail: str(data['message'], 'fos.farm.link_plot'.tr()),
          action: FilledButton.tonal(
              onPressed: () => context.push('/notebook?tab=fields'),
              child: Text('fos.farm.open_fields'.tr())),
        ),
      ]);
    }
    final live = asMap(data['live']);
    final current = asMap(live['current']);
    final daily = asMap(live['daily']);
    final hourly = asMap(live['hourly']);
    final air = asMap(live['air']);
    final forecast = asMap(data['forecast']);
    final records = asMaps(forecast['records']);
    final days = <(String, num?, num?, num?, num?, num?)>[];
    final times = (daily['time'] as List? ?? const []);
    if (times.isNotEmpty) {
      for (var i = 0; i < times.length && i < 10; i++) {
        num? at(String k) => (daily[k] as List?)?.elementAtOrNull(i) as num?;
        days.add((
          '${times[i]}',
          at('temperature_2m_min'),
          at('temperature_2m_max'),
          at('precipitation_sum'),
          at('precipitation_probability_max'),
          at('weather_code')
        ));
      }
    } else {
      for (final r in records.take(10)) {
        days.add((
          str(r['valid_on']),
          r['temperature_min_c'] as num?,
          r['temperature_max_c'] as num?,
          r['rainfall_mm'] as num?,
          null,
          null
        ));
      }
    }
    final hours = <(String, num?, num?, num?)>[];
    final hTimes =
        (hourly['time'] as List? ?? const []).map((e) => '$e').toList();
    final startAt =
        hTimes.indexWhere((t) => t.compareTo(str(current['time'])) >= 0);
    if (startAt >= 0) {
      for (var i = startAt; i < hTimes.length && i < startAt + 12; i++) {
        num? at(String k) => (hourly[k] as List?)?.elementAtOrNull(i) as num?;
        hours.add((
          hTimes[i],
          at('temperature_2m'),
          at('precipitation_probability'),
          at('weather_code')
        ));
      }
    }
    String v(Object? x, [String unit = '']) =>
        x is num ? '${x.round()}$unit' : '—';
    final source = str(
        live['source'],
        str(asMap(forecast['provenance'])['source'],
            'fos.farm.regional_forecast'.tr()));
    String? headline;
    if (days.isNotEmpty) {
      final lang = context.locale.languageCode;
      headline = 'fos.farm2.wx_no_rain'.tr();
      for (var i = 0; i < days.length && i < 3; i++) {
        final mm = days[i].$4;
        if (mm != null && mm >= 1) {
          final args = {'mm': mm.toStringAsFixed(mm >= 10 ? 0 : 1)};
          final dt = DateTime.tryParse(days[i].$1);
          headline = i == 0
              ? 'fos.farm2.wx_rain_today'.tr(namedArgs: args)
              : i == 1
                  ? 'fos.farm2.wx_rain_tomorrow'.tr(namedArgs: args)
                  : 'fos.farm2.wx_rain_on'.tr(namedArgs: {
                      ...args,
                      'day': dt == null
                          ? days[i].$1
                          : DateFormat.EEEE(lang).format(dt)
                    });
          break;
        }
      }
    }
    return ListView(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 96),
        children: [
          if (headline != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(4, 4, 4, 10),
              child: Text(headline,
                  style: TextStyle(
                      fontSize: 20, fontWeight: FontWeight.w700, color: ink)),
            ),
          FarmCard(
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(
                  child: Text(
                      cityName ??
                          str(
                              forecast['farm'],
                              str(asMap(data['city'])['name'],
                                  'fos.farm.your_farm'.tr())),
                      style: TextStyle(
                          fontWeight: FontWeight.w700,
                          fontSize: 16,
                          color: ink)),
                ),
                ProvenanceBadge({
                  'origin': current.isEmpty ? 'forecast' : 'modeled',
                  'source': source
                }),
              ]),
              const SizedBox(height: 8),
              Row(children: [
                Icon(weatherIcon(current['weather_code'] as num?),
                    size: 46,
                    color: context.isDark
                        ? AppColors.primaryLight
                        : AppColors.primaryDark),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(v(current['temperature_2m'], '°C'),
                            style: TextStyle(
                                fontSize: 34,
                                fontWeight: FontWeight.w700,
                                color: ink)),
                        Text(
                            'fos.farm.condition_feels'.tr(namedArgs: {
                              'condition':
                                  weatherLabel(current['weather_code'] as num?),
                              'temp': v(current['apparent_temperature'], '°')
                            }),
                            style: TextStyle(color: mutedColor(context))),
                      ]),
                ),
              ]),
              const SizedBox(height: 8),
              Wrap(spacing: 14, runSpacing: 6, children: [
                Text(
                    'fos.farm.humidity_value'.tr(namedArgs: {
                      'value': v(current['relative_humidity_2m'], '%')
                    }),
                    style: TextStyle(color: ink)),
                Text(
                    'fos.farm.wind_gusts'.tr(namedArgs: {
                      'speed': v(current['wind_speed_10m'], ' km/h'),
                      'gusts': v(current['wind_gusts_10m'])
                    }),
                    style: TextStyle(color: ink)),
                Text(
                    'fos.farm.rain_now'.tr(namedArgs: {
                      'value': '${current['precipitation'] ?? '—'}'
                    }),
                    style: TextStyle(color: ink)),
                if (air['us_aqi'] is num)
                  Text(
                      'fos.farm.aqi_value'.tr(namedArgs: {
                        'value': v(air['us_aqi']),
                        'band': aqiBand(air['us_aqi'] as num)
                      }),
                      style: TextStyle(color: ink)),
              ]),
            ]),
          ),
          if (str(data['live_error']).isNotEmpty)
            Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text(str(data['live_error']),
                    style: TextStyle(color: mutedColor(context)))),
          SectionTitle('fos.farm.next_hours'.tr()),
          if (hours.isEmpty)
            Text('fos.farm.hourly_unavailable'.tr(),
                style: TextStyle(color: mutedColor(context)))
          else
            SizedBox(
              height: 104 * MediaQuery.textScalerOf(context).scale(1),
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: hours.length,
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemBuilder: (_, i) {
                  final (t, temp, pop, code) = hours[i];
                  return SizedBox(
                    width: 70,
                    child: FarmCard(
                      padding: const EdgeInsets.all(8),
                      child: Column(children: [
                        Text(t.length >= 16 ? t.substring(11, 16) : t,
                            style: TextStyle(
                                fontSize: 12, color: mutedColor(context))),
                        Icon(weatherIcon(code),
                            size: 22,
                            color: context.isDark
                                ? AppColors.primaryLight
                                : AppColors.primaryDark),
                        Text(v(temp, '°'),
                            style: TextStyle(
                                fontWeight: FontWeight.w700, color: ink)),
                        Text(pop == null ? '—' : '${pop.round()}%',
                            style: const TextStyle(
                                fontSize: 12, color: AppColors.info)),
                      ]),
                    ),
                  );
                },
              ),
            ),
          const SizedBox(height: 16),
          _WeatherPlan(current: current, days: days, cityName: cityName),
          SectionTitle('fos.farm.days_ahead'.tr()),
          for (final (date, min, max, rain, pop, code) in days)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: FarmCard(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                child: Row(children: [
                  SizedBox(
                    width: 92,
                    child: Text(
                      DateTime.tryParse(date) == null
                          ? date
                          : DateFormat('EEE d MMM', context.locale.toString())
                              .format(DateTime.parse(date)),
                      style: TextStyle(color: ink),
                    ),
                  ),
                  Icon(weatherIcon(code),
                      size: 20,
                      color: context.isDark
                          ? AppColors.primaryLight
                          : AppColors.primaryDark),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '${rain == null ? '—' : '${rain.toStringAsFixed(1)} mm'}${pop == null ? '' : ' · ${pop.round()}%'}',
                      style: TextStyle(color: mutedColor(context)),
                    ),
                  ),
                  Text('${v(min, '°')} / ${v(max, '°')}',
                      style:
                          TextStyle(fontWeight: FontWeight.w600, color: ink)),
                ]),
              ),
            ),
          const SizedBox(height: 8),
          Text('fos.farm2.wx_note'.tr(),
              style: TextStyle(fontSize: 12, color: mutedColor(context))),
        ]);
  }
}

class _CitySearch extends ConsumerStatefulWidget {
  const _CitySearch();

  @override
  ConsumerState<_CitySearch> createState() => _CitySearchState();
}

class _CitySearchState extends ConsumerState<_CitySearch> {
  Timer? _debounce;
  List<Map<String, dynamic>> _cities = const [];
  bool _busy = false;
  String? _message;

  void _search(String q) {
    _debounce?.cancel();
    if (q.trim().length < 2) return;
    _debounce = Timer(const Duration(milliseconds: 300), () async {
      setState(() => _busy = true);
      try {
        final data = asMap(await ref
            .read(apiProvider)
            .get('/api/weather/cities', query: {'q': q.trim()}));
        setState(() {
          _cities = asMaps(data['cities']);
          _message = _cities.isEmpty ? 'fos.farm.no_cities'.tr() : null;
        });
      } catch (e) {
        setState(() => _message = '$e');
      } finally {
        if (mounted) setState(() => _busy = false);
      }
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.fromLTRB(
            16, 16, 16, MediaQuery.viewInsetsOf(context).bottom + 16),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          TextField(
            autofocus: true,
            onChanged: _search,
            decoration: InputDecoration(
                labelText: 'fos.farm.city'.tr(),
                hintText: 'fos.farm.city_hint'.tr(),
                prefixIcon: const Icon(Icons.search)),
          ),
          if (_busy) const LinearProgressIndicator(),
          if (_message != null)
            Padding(padding: const EdgeInsets.all(12), child: Text(_message!)),
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 360),
            child: ListView(shrinkWrap: true, children: [
              for (final c in _cities)
                ListTile(
                  title: Text(str(c['name'])),
                  subtitle: Text([c['admin1'], c['country']]
                      .where((e) => e != null)
                      .join(', ')),
                  onTap: () => Navigator.pop(context, c),
                ),
            ]),
          ),
        ]),
      );
}


class _WeatherPlan extends ConsumerWidget {
  const _WeatherPlan({required this.current, required this.days, this.cityName});
  final Map<String, dynamic> current;
  final List<(String, num?, num?, num?, num?, num?)> days;
  final String? cityName;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rain = days.isNotEmpty ? days.first.$4 : null;
    final hot = (current['temperature_2m'] as num? ?? 0) >= 35;
    final title = rain != null && rain >= 1 ? 'Make room for the rain.' : hot ? 'Plan around the afternoon heat.' : 'A good moment to check your field.';
    final steps = <String>[
      if (rain != null && rain >= 1) 'Keep harvested produce covered and check that drains are clear.'
      else if (hot) 'Move strenuous outdoor work to cooler hours and keep drinking water nearby.'
      else 'Check soil moisture in the field before deciding whether to irrigate.',
      'Review the next-hour forecast before setting the timing of outdoor work.',
    ];
    return FarmCard(color: context.isDark ? AppColors.darkCard : const Color(0xFFF0EEE7), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('PREPARED BY MITRA', style: TextStyle(fontSize: 10, letterSpacing: 1.3, fontWeight: FontWeight.w600, color: accentColor(context))),
      const SizedBox(height: 8), Text(title, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w600)),
      for (final step in steps) Padding(padding: const EdgeInsets.only(top: 8), child: Text('• $step', style: const TextStyle(fontSize: 13, height: 1.5))),
      TextButton.icon(icon: const Icon(Icons.edit_note, size: 18), label: const Text('Make this my plan'), onPressed: () {
        showHelperSheet(context, 'weather', runContext: RunContext(view: 'weather', weatherCity: cityName));
        ref.read(assistantProvider.notifier).send('Help me review this weather-based plan for my farm: $title ${steps.join(' ')} Check current conditions and my crop before proposing tasks. Ask me to approve before saving.', context: RunContext(view: 'weather', weatherCity: cityName));
      }),
    ]));
  }
}
