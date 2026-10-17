import '../tour/app_tour.dart';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../assistant/assistant_controller.dart';
import '../core/session.dart';
import '../ui/kit.dart';
import '../ui/loader.dart';
import '../ui/mitra_orb.dart';
import '../utils/constants.dart';
import '../voice/live_voice.dart';
import '../voice/speech.dart';
import '../features/workspace_tools.dart';
import '../core/workspace_cache.dart';
import '../features/saathi.dart';

const _destinations = <(String, String, IconData, String)>[
  ('Weather', 'Plan around the sky', Icons.wb_sunny_outlined, '/weather'),
  (
    'My tasks',
    'One thing at a time',
    Icons.event_available_outlined,
    '/calendar'
  ),
  ('Crop doctor', 'A closer look at your crop', Icons.eco_outlined, '/crops'),
  ('Mandi prices', 'Know your market', Icons.show_chart_rounded, '/markets'),
  ('Notebook', 'Your farm, remembered', Icons.menu_book_outlined, '/notebook'),
  (
    'Farm station',
    'Know what your field feels',
    Icons.sensors_outlined,
    '/station'
  ),
  (
    'Farmer exchange',
    'Grow with your neighbours',
    Icons.handshake_outlined,
    '/exchange'
  ),
  (
    'Schemes',
    'Support worth exploring',
    Icons.account_balance_outlined,
    '/schemes'
  ),
];

class ChoiceScreen extends ConsumerStatefulWidget {
  const ChoiceScreen({super.key});
  @override
  ConsumerState<ChoiceScreen> createState() => _ChoiceScreenState();
}

class _ChoiceScreenState extends ConsumerState<ChoiceScreen> {
  Map<String, dynamic> _profile = {};
  @override
  void initState() {
    super.initState();
    _prepare();
  }

  Future<void> _prepare() async {
    final api = ref.read(apiProvider);
    // Warm the assistant immediately; it stays alive while routes change.
    ref.read(assistantProvider);
    unawaited(ref
        .read(speechCapabilitiesProvider.future)
        .then((_) {}, onError: (Object _) {}));
    try {
      final p = asMap(asMap(await api.get('/api/profile'))['profile']);
      if (!mounted) return;
      setState(() => _profile = p);
    } catch (_) {}
    if (!mounted) return;
    final tools = ref.read(workspaceToolsProvider);
    final args = <String, Object?>{'commodity': (_profile['crops'] as List? ?? ['Wheat']).firstOrNull ?? 'Wheat', 'state': str(_profile['state']), 'observed_only': ref.read(authProvider).mode != BackendMode.demo};
    unawaited(Future.wait([
      tools.inspect('market_prices', args).catchError((_) => <String,dynamic>{}),
      tools.inspect('market_trend', args).catchError((_) => <String,dynamic>{}),
    ]));
    unawaited(ref.cachedGet('/api/mandi/catalogue', query: {'limit': 200}).then((_) {}, onError: (_) {}));
    unawaited(_warmPlans());
    // Bounded read prefetch continues even if a particular source is offline.
    for (final group in [
      ['/api/farm-workspace/today', '/api/farm-workspace/missions'],
      ['/api/weather/dashboard', '/api/companion'],
      ['/api/farms', '/api/plots'],
      ['/api/crop-cycles', '/api/onboarding/options'],
      ['/api/farm-workspace/ledger', '/api/farm-workspace/cases'],
      ['/api/exchange/listings', '/api/sensors/stations'],
    ]) {
      if (!mounted) return;
      await Future.wait(group.map((path) async {
        try {
          await api.get(path);
        } catch (_) {}
      }));
    }
  }

  Future<void> _warmPlans() async {
    final api = ref.read(apiProvider);
    for (final area in ['today', 'markets', 'schemes', 'records', 'crops', 'exchange']) {
      if (!mounted) return;
      try {
        final data = asMap(await api.get('/api/companion/proposals', query: {'area': area}));
        final job = asMap(data['job']);
        if (asMaps(data['proposals']).isEmpty && !{'queued', 'running', 'failed'}.contains(job['state'])) {
          await api.post('/api/companion/prepare', body: {'area': area, 'research': false});
        }
      } catch (_) {}
    }
  }

  @override
  Widget build(BuildContext context) {
    final assistant = ref.watch(assistantProvider);
    final name = str(_profile['name']).split(' ').first;
    return Scaffold(
        body: FarmBackground(
            child: SafeArea(
                child: ListView(
                  key: const PageStorageKey('home'),
                    padding: const EdgeInsets.fromLTRB(24, 16, 24, 32),
                    children: [
          Row(children: [
            const Icon(Icons.eco_rounded, color: AppColors.primary),
            const SizedBox(width: 8),
            const Text('kisan mitra',
                style: TextStyle(
                    fontWeight: FontWeight.w700,
                    fontSize: 17,
                    letterSpacing: -.5)),
            const Spacer(),
            const TourReplayButton(),
            TourAnchor(id: 'profile', child: IconButton(
                tooltip: 'Your profile',
                onPressed: () => context.push('/profile'),
                icon: const Icon(Icons.person_outline_rounded))),
          ]),
          const SizedBox(height: 28),
          Text(
              name.isEmpty
                  ? 'A little help.\nA better farm day.'
                  : 'Hello, $name.\nLet’s grow something good.',
              style: const TextStyle(
                  fontSize: 30,
                  height: 1.2,
                  fontWeight: FontWeight.w600,
                  letterSpacing: -1)),
          const SizedBox(height: 12),
          Text(str(_profile['location'], 'Your farm companion, always close.'),
              style: TextStyle(color: mutedColor(context), fontSize: 14)),
          const SizedBox(height: 28),
          TourAnchor(id: 'voice', child: FarmCard(
              color:
                  context.isDark ? AppColors.darkCard : const Color(0xFFEAEEDD),
              padding: const EdgeInsets.fromLTRB(22, 12, 12, 20),
              onTap: () => openLiveVoice(context),
              child: Row(children: [
                Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      const Text('A FRIEND IN YOUR FIELD',
                          style: TextStyle(
                              fontSize: 9,
                              letterSpacing: 1.4,
                              fontWeight: FontWeight.w700)),
                      const SizedBox(height: 18),
                      const Text('Talk to Mitra',
                          style: TextStyle(
                              fontSize: 23, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 8),
                      Text('Speak freely, in your language.',
                          style: TextStyle(
                              color: mutedColor(context), height: 1.5)),
                      const SizedBox(height: 18),
                      const Row(children: [
                        Icon(Icons.graphic_eq, size: 18),
                        SizedBox(width: 8),
                        Flexible(
                            child: Text('Start a conversation',
                                style: TextStyle(
                                    fontSize: 12, fontWeight: FontWeight.w600)))
                      ]),
                    ])),
                const MitraOrb(size: 130),
              ]))),
          const SizedBox(height: 12),
          TourAnchor(id: 'chat', child: FarmCard(
              onTap: () => context.push('/chat'),
              child: Row(children: [
                const Icon(Icons.edit_note_rounded),
                const SizedBox(width: 14),
                Expanded(
                    child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                      const Text('Prefer to type?',
                          style: TextStyle(fontWeight: FontWeight.w600)),
                      Text(
                          assistant.busy
                              ? 'Mitra is working. Open your conversation.'
                              : 'Your thoughts, questions and plans.',
                          style: TextStyle(
                              fontSize: 12, color: mutedColor(context))),
                    ])),
                const Icon(Icons.arrow_forward_rounded, size: 18),
              ]))),
          const SizedBox(height: 22),
          const PreparedBySaathi(area: 'today'),
          SectionTitle('A little ahead of your day',
              eyebrow: 'SAATHI',
              trailing: IconButton(
                  tooltip: 'Open Saathi',
                  onPressed: () => context.push('/saathi'),
                  icon: const Icon(Icons.arrow_outward))),
          FarmCard(
              onTap: () => context.push('/calendar'),
              child: Row(children: [
                const Icon(Icons.event_available_outlined),
                const SizedBox(width: 14),
                Expanded(
                    child: Text(assistant.tasks.isEmpty
                        ? 'Build your first farm routine with Mitra.'
                        : '${assistant.tasks.length} saved tasks. Pick up where you left off.'))
              ])),
          const SizedBox(height: 14),
          const TourAnchor(id: 'tools', child: SectionTitle('Everything for your farm',
              eyebrow: 'YOUR TOOLSHED')),
          LayoutBuilder(
              builder: (context, box) =>
                  Wrap(spacing: 12, runSpacing: 12, children: [
                    for (final (title, subtitle, icon, path) in _destinations)
                      SizedBox(
                          width: (box.maxWidth - 12) / 2,
                          child: FarmCard(
                              padding: const EdgeInsets.all(16),
                              onTap: () {
                                HapticFeedback.selectionClick();
                                context.push(path);
                              },
                              child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Icon(icon,
                                        color: accentColor(context), size: 25),
                                    const SizedBox(height: 18),
                                    Text(title,
                                        style: const TextStyle(
                                            fontWeight: FontWeight.w600,
                                            fontSize: 14)),
                                    const SizedBox(height: 5),
                                    Text(subtitle,
                                        style: TextStyle(
                                            color: mutedColor(context),
                                            fontSize: 11,
                                            height: 1.5)),
                                  ]))),
                  ])),
          const SizedBox(height: 24),
          TextButton.icon(
              onPressed: () => context.push('/onboarding'),
              icon: const Icon(Icons.tune_rounded, size: 18),
              label: const Text('Make this farm yours')),
        ]))));
  }
}
