import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:geocoding/geocoding.dart';
import 'package:go_router/go_router.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../core/session.dart';
import '../core/onboarding_progress.dart';
import 'splash_screen.dart';
import '../core/language.dart';
import '../ui/kit.dart';
import '../ui/loader.dart';
import '../ui/mitra_orb.dart';
import '../voice/voice_button.dart';
import '../voice/speech.dart';
import '../features/starter_plans.dart';

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});
  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  int _step = 0;
  OnboardingProgress? _progress;
  bool _restoring = true, _resumed = false;
  Future<void> _writes = Future.value();

  Future<void> _remember() {
    if (_restoring || _progress == null) return Future.value();
    final draft = <String, dynamic>{
      'step': _step, 'name': _name.text, 'place': _place.text,
      'farm': _farm.text, 'area': _area.text, 'crops': _crops.text,
      'region': _region, 'regions': _regions, 'ownership': _ownership,
      'irrigation': _irrigation, 'saveRoutines': _saveRoutines,
      'farmId': _farmId, 'plotId': _plotId,
    };
    _writes = _writes.then((_) => _progress!.write(draft)).catchError((Object _) {
      if (mounted) setState(() => _error = 'Could not keep this draft on your phone. Please try again.');
    });
    return _writes;
  }

  void _change(VoidCallback action) {
    setState(action);
    unawaited(_remember());
  }

  bool _busy = false, _atFarm = false, _saveRoutines = true;
  String? _error, _region, _farmId, _plotId;
  Position? _position;
  List<Map<String, dynamic>> _regions = [];
  final _name = TextEditingController(),
      _place = TextEditingController(),
      _farm = TextEditingController(),
      _area = TextEditingController(),
      _crops = TextEditingController();
  String _irrigation = 'rainfed', _ownership = 'owned';
  static const _titles = [
    'Make yourself at home.',
    'Your corner of the world.',
    'Let’s meet your farm.',
    'A little head start.'
  ];
  static const _notes = [
    'I’m Mitra. Tell me your name, or tap the microphone. We’ll take this one small step at a time.',
    'Use your phone’s location for nearby weather. You can change it, or skip for now.',
    'Only you know your land best. Add what you know; everything else can wait.',
    'Review your details. Your starter routines are ready to customise, and nothing is saved until you choose.'
  ];
  @override
  void initState() {
    super.initState();
    for (final c in [_name, _place, _farm, _area, _crops]) {
      c.addListener(_remember);
    }
    _load();
  }

  Future<void> _load() async {
    Map<String, dynamic>? draft;
    try {
      final prefs = await SharedPreferences.getInstance();
      if (!mounted) return;
      final sid = ref.read(authProvider).session?.id ?? ref.read(apiProvider).session?.id;
      if (sid != null) {
        _progress = OnboardingProgress(prefs, sid);
        draft = _progress!.read();
      }
      if (draft == null) {
      final api = ref.read(apiProvider);
      final values = await Future.wait([
        api.get('/api/onboarding/options', timeout: const Duration(seconds: 5)),
        api.get('/api/profile', timeout: const Duration(seconds: 5))]);
      if (!mounted) return;
      final p = asMap(asMap(values[1])['profile']);
      _regions = asMaps(asMap(values[0])['regions']);
      _name.text = str(p['name']);
      _place.text = str(p['location']);
      _region = _regions.where((r) => r['name'] == p['state'])
          .map((r) => str(r['id'])).firstOrNull;
      _area.text = p['land_size_acres'] is num
          ? ((p['land_size_acres'] as num) / 2.47105).toStringAsFixed(2) : '';
      _crops.text = p['crops'] is List ? (p['crops'] as List).join(', ') : '';
      }
    } catch (_) {
      _error = 'Could not refresh your details. Your saved draft is still here.';
    } finally {
      if (mounted) {
        if (draft != null) {
          _step = (draft['step'] as int? ?? 0).clamp(0, 3);
          _name.text = str(draft['name']); _place.text = str(draft['place']);
          _farm.text = str(draft['farm']); _area.text = str(draft['area']);
          _crops.text = str(draft['crops']);
          if (_regions.isEmpty) _regions = asMaps(draft['regions']);
          _region = _regions.any((r) => r['id'] == draft!['region']) ? draft['region'] as String? : null;
          _ownership = str(draft['ownership'], 'owned');
          _irrigation = str(draft['irrigation'], 'rainfed');
          _saveRoutines = draft['saveRoutines'] != false;
          _farmId = draft['farmId'] as String?; _plotId = draft['plotId'] as String?;
          _resumed = true;
        }
        setState(() => _restoring = false);
        await _remember();
      }
    }
  }

  Future<void> _locate() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      var permission = await Geolocator.checkPermission();
      if (permission == LocationPermission.denied) {
        permission = await Geolocator.requestPermission();
      }
      if (permission == LocationPermission.denied ||
          permission == LocationPermission.deniedForever) {
        throw StateError(
            'Location is optional. Choose your state below, or skip.');
      }
      final position = await Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(
              accuracy: LocationAccuracy.medium,
              timeLimit: Duration(seconds: 12)));
      final places = await Geocoding()
          .placemarkFromCoordinates(position.latitude, position.longitude);
      if (!mounted) return;
      final place = places.firstOrNull;
      setState(() {
        _position = position;
        _place.text = [place?.locality, place?.subAdministrativeArea]
            .whereType<String>()
            .where((s) => s.isNotEmpty)
            .toSet()
            .join(', ');
        _region = _regions
            .where((r) =>
                str(r['name']).toLowerCase() ==
                (place?.administrativeArea ?? '').toLowerCase())
            .map((r) => str(r['id']))
            .firstOrNull;
      });
    } catch (e) {
      if (mounted) {
        setState(() => _error = e is StateError
            ? e.message.toString()
            : 'Location could not be found. You can enter your place instead.');
      }
    } finally {
      if (mounted) { setState(() => _busy = false); await _remember(); }
    }
  }

  Future<void> _leave({bool completed = false}) async {
    await _remember();
    await _progress?.leave(completed: completed);
    if (mounted) context.go('/');
  }

  Future<void> _save() async {
    if (_name.text.trim().length < 2 || _region == null) {
      setState(() {
        _error = 'Add your name and choose a state before saving.';
        _step = _name.text.trim().length < 2 ? 0 : 1;
      });
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final api = ref.read(apiProvider);
      await api.post('/api/onboarding', body: {
        'display_name': _name.text.trim(),
        'region_id': _region,
        'preferred_language': ref.read(languageProvider).code,
        'consent_to_store_profile': true
      });
      await api.post('/api/profile/save', body: {
        'name': _name.text.trim(),
        'location': _place.text.trim(),
        'crops': _crops.text
            .split(',')
            .map((s) => s.trim())
            .where((s) => s.isNotEmpty)
            .toList(),
        'preferred_language': ref.read(languageProvider).code,
        if ((double.tryParse(_area.text) ?? 0) > 0)
          'land_size_acres': double.parse(_area.text) * 2.47105
      });
      if (_farm.text.trim().length >= 2 && _farmId == null) {
        final result = asMap(await api.post('/api/farms', body: {
          'name': _farm.text.trim(),
          'region_id': _region,
          'ownership_type': _ownership,
          'irrigation_method': _irrigation
        }));
        _farmId = str(result['id']);
        await _remember();
      }
      final hectares = double.tryParse(_area.text);
      if (_farmId != null &&
          _plotId == null &&
          _atFarm &&
          _position != null &&
          hectares != null &&
          hectares > 0) {
        final result = asMap(await api.post('/api/plots', body: {
          'farm_id': _farmId,
          'name': '${_farm.text.trim()} field',
          'area_ha': hectares,
          'latitude': double.parse(_position!.latitude.toStringAsFixed(6)),
          'longitude': double.parse(_position!.longitude.toStringAsFixed(6))
        }));
        _plotId = str(result['id']);
        await _remember();
      }
      if (_saveRoutines) {
        await api
            .post('/api/onboarding/starter-plans', body: {'approved': true});
      }
      api.invalidateReads();
      await _leave(completed: true);
    } catch (_) {
      if (mounted) {
        setState(() => _error =
            'Some details could not be saved. Your entries are kept here; retry to finish.');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _field(TextEditingController c, String label, {bool number = false}) =>
      Padding(
          padding: const EdgeInsets.only(bottom: 16),
          child: TextField(
              controller: c,
              keyboardType: number
                  ? const TextInputType.numberWithOptions(decimal: true)
                  : TextInputType.text,
              decoration: InputDecoration(
                  labelText: label,
                  suffixIcon:
                      VoiceButton(onTranscript: (text) => c.text = text))));
  @override
  void dispose() {
    for (final c in [_name, _place, _farm, _area, _crops]) {
      c.dispose();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => _restoring ? const SplashScreen() : Scaffold(
          body: FarmBackground(
              child: SafeArea(
                  child: Column(children: [
        Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
            child: Row(children: [
              if (_step > 0)
                IconButton(
                    tooltip: MaterialLocalizations.of(context).backButtonTooltip,
                    onPressed: _busy ? null : () => _change(() => _step--),
                    icon: const Icon(Icons.arrow_back)),
              Flexible(
                  child: Text('YOUR FARM, YOUR WAY',
                      style: TextStyle(
                          fontSize: 10,
                          letterSpacing: 2,
                          color: mutedColor(context)))),
              const Spacer(),
              TextButton(
                  onPressed: _busy ? null : _leave,
                  child: const Text('Skip for now')),
            ])),
        Padding(
            padding: const EdgeInsets.symmetric(horizontal: 28),
            child: LinearProgressIndicator(
                value: (_step + 1) / 4,
                minHeight: 3,
                borderRadius: BorderRadius.circular(8))),
        Expanded(
            child: SingleChildScrollView(
                padding: const EdgeInsets.all(28),
                child: AnimatedSwitcher(
                    duration: MediaQuery.disableAnimationsOf(context) ? Duration.zero : const Duration(milliseconds: 250),
                    layoutBuilder: (current, previous) => Stack(alignment: Alignment.topLeft, children: [...previous, if (current != null) current]),
                    child: Column(
                        key: ValueKey(_step),
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (_step == 0)
                            const Center(child: MitraOrb(size: 150)),
                          if (_resumed) ...[
                            Text('WELCOME BACK · DRAFT SAVED ON THIS PHONE', style: TextStyle(fontSize: 10, letterSpacing: 1, color: mutedColor(context))),
                            const SizedBox(height: 14),
                          ],
                          Text(_titles[_step],
                              style: const TextStyle(
                                  fontSize: 29,
                                  height: 1.2,
                                  fontWeight: FontWeight.w600)),
                          const SizedBox(height: 14),
                          Text(_notes[_step],
                              style: TextStyle(
                                  fontSize: 15,
                                  height: 1.6,
                                  color: mutedColor(context))),
                          TextButton.icon(
                              onPressed: () async {
                                try {
                                  await ref.read(speechProvider).speak(
                                      _notes[_step],
                                      speechLanguageFor(_notes[_step],
                                          ref.read(languageProvider).code));
                                } catch (_) {
                                  if (context.mounted) {
                                    showNotice(context,
                                        'Voice is unavailable right now. You can continue by typing.');
                                  }
                                }
                              },
                              icon: const Icon(Icons.volume_up_outlined,
                                  size: 18),
                              label: const Text('Read this to me')),
                          const SizedBox(height: 20),
                          if (_step == 0)
                            _field(_name, 'What should I call you?'),
                          if (_step == 1) ...[
                            FilledButton.icon(
                                onPressed: _busy ? null : _locate,
                                icon: const Icon(Icons.my_location),
                                label: Text(_busy
                                    ? 'Finding your place…'
                                    : 'Use my location')),
                            const SizedBox(height: 20),
                            _field(_place, 'Village or town'),
                            DropdownButtonFormField<String>(
                                initialValue: _region,
                                isExpanded: true,
                                decoration:
                                    const InputDecoration(labelText: 'State'),
                                items: [
                                  for (final r in _regions)
                                    DropdownMenuItem(
                                        value: str(r['id']),
                                        child: Text(str(r['name'])))
                                ],
                                onChanged: (v) => _change(() => _region = v)),
                          ],
                          if (_step == 2) ...[
                            _field(_farm, 'Farm name (optional)'),
                            _field(_crops, 'Your crops, separated by commas'),
                            _field(_area, 'Field area in hectares (optional)',
                                number: true),
                            DropdownButtonFormField<String>(
                                initialValue: _ownership,
                                decoration: const InputDecoration(
                                    labelText: 'Your land'),
                                items: [
                                  for (final s in ['owned', 'leased', 'shared'])
                                    DropdownMenuItem(value: s, child: Text(s))
                                ],
                                onChanged: (v) => _change(() => _ownership = v!)),
                            const SizedBox(height: 16),
                            DropdownButtonFormField<String>(
                                initialValue: _irrigation,
                                decoration: const InputDecoration(
                                    labelText: 'Watering method'),
                                items: [
                                  for (final s in [
                                    'rainfed',
                                    'drip',
                                    'sprinkler',
                                    'flood',
                                    'manual',
                                    'other'
                                  ])
                                    DropdownMenuItem(value: s, child: Text(s))
                                ],
                                onChanged: (v) => _change(() => _irrigation = v!)),
                            if (_position != null)
                              CheckboxListTile(
                                  contentPadding: EdgeInsets.zero,
                                  value: _atFarm,
                                  onChanged: (v) =>
                                      setState(() => _atFarm = v!),
                                  title: const Text('I am at this field'),
                                  subtitle: const Text(
                                      'Use this position for the field. Your phone location may be different from your farm.')),
                          ],
                          if (_step == 3) ...[
                            FarmCard(
                                child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                  Text(_name.text,
                                      style: const TextStyle(
                                          fontSize: 22,
                                          fontWeight: FontWeight.w600)),
                                  Text(_place.text),
                                  if (_area.text.isNotEmpty)
                                    Text(
                                        '${_area.text} hectares (self-reported)'),
                                  if (_farm.text.isNotEmpty)
                                    Text(
                                        '${_farm.text} · $_ownership · $_irrigation'),
                                  if (_crops.text.isNotEmpty) Text(_crops.text),
                                  const SizedBox(height: 12),
                                  const Text(
                                      'Save my profile and the farm details shown here. You can edit these any time.'),
                                ])),
                            const SizedBox(height: 20),
                            const StarterPlans(compact: true),
                            CheckboxListTile(
                                contentPadding: EdgeInsets.zero,
                                value: _saveRoutines,
                                onChanged: (value) =>
                                    _change(() => _saveRoutines = value!),
                                title: const Text(
                                    'Add these starter drafts to my notebook'),
                                subtitle: const Text(
                                    'You can edit or remove them. Nothing is marked as done.')),
                          ],
                          if (_error != null)
                            ErrorView(_error!, onRetry: _load),
                        ])))),
        Padding(
            padding: const EdgeInsets.fromLTRB(28, 8, 28, 24),
            child: SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _busy
                      ? null
                      : () {
                          HapticFeedback.selectionClick();
                          if (_step < 3) {
                            _change(() => _step++);
                          } else {
                            _save();
                          }
                        },
                  child: Text(_step == 3 ? 'Save & open my farm' : 'Continue'),
                ))),
      ]))));
}
