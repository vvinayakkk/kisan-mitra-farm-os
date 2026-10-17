import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../core/session.dart';
import '../services/theme_service.dart';
import '../ui/kit.dart';
import '../ui/loader.dart';
import '../utils/constants.dart';
import '../voice/live_voice.dart';

/// Home: voice or text, plus quick services (the original app layout).
class ChoiceScreen extends ConsumerStatefulWidget {
  const ChoiceScreen({super.key});

  @override
  ConsumerState<ChoiceScreen> createState() => _ChoiceScreenState();
}

class _ChoiceScreenState extends ConsumerState<ChoiceScreen> {
  String? _location;

  @override
  void initState() {
    super.initState();
    _loadLocation();
  }

  // The farm location comes from the server profile, not the device GPS.
  Future<void> _loadLocation() async {
    try {
      final profile = asMap(asMap(await ref.read(apiProvider).get('/api/profile'))['profile']);
      final place = '${profile['location'] ?? profile['state'] ?? ''}';
      if (mounted && place.isNotEmpty) setState(() => _location = place);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final dark = context.isDark;
    final ink = inkColor(context);
    const iconColor = Color(0xFF2E7D32);
    return Scaffold(
      body: FarmBackground(
        child: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Column(children: [
              const SizedBox(height: 12),
              Row(children: [
                if (_location != null)
                  SizedBox(
                    width: 170,
                    child: GestureDetector(
                      onTap: () => context.push('/profile'),
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
                        decoration: BoxDecoration(
                          color: glassFill(dark),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: glassBorder(dark)),
                        ),
                        child: Row(mainAxisSize: MainAxisSize.min, children: [
                          Icon(Icons.location_on_outlined, size: 18, color: ink),
                          const SizedBox(width: 6),
                          Flexible(
                            child: Text(_location!,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: ink)),
                          ),
                        ]),
                      ),
                    ),
                  ),
                const Spacer(),
                _TopIcon(dark ? Icons.dark_mode_rounded : Icons.light_mode_rounded, ink,
                    () => ref.read(themeProvider.notifier).toggle()),
                const SizedBox(width: 8),
                _TopIcon(Icons.person_outline_rounded, ink, () => context.push('/profile')),
                const SizedBox(width: 8),
                _TopIcon(Icons.logout_rounded, AppColors.error, () => ref.read(authProvider.notifier).signOut()),
              ]),
              const SizedBox(height: 30),
              SizedBox(
                height: 210,
                width: 210,
                child: ClipOval(child: Image.asset(dark ? 'assets/logo_light.png' : 'assets/logo.png', fit: BoxFit.contain)),
              ),
              const SizedBox(height: 16),
              Text('choice.title'.tr(),
                  textAlign: TextAlign.center, style: TextStyle(fontWeight: FontWeight.w700, fontSize: 22, color: ink)),
              const SizedBox(height: 24),
              _ModeCard(
                icon: Icons.mic_rounded,
                iconColor: iconColor,
                title: 'choice.voice_title'.tr(),
                subtitle: 'choice.voice_subtitle'.tr(),
                onTap: () => openLiveVoice(context),
              ),
              const SizedBox(height: 20),
              Row(children: [
                const Expanded(child: Divider()),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  child: Text('choice.or'.tr(), style: TextStyle(fontWeight: FontWeight.w600, color: mutedColor(context))),
                ),
                const Expanded(child: Divider()),
              ]),
              const SizedBox(height: 20),
              _ModeCard(
                icon: Icons.edit_note_rounded,
                iconColor: iconColor,
                title: 'choice.chat_title'.tr(),
                subtitle: 'choice.chat_subtitle'.tr(),
                onTap: () => context.push('/chat'),
              ),
              const SizedBox(height: 24),
              Text('choice.quick_services'.tr(), style: TextStyle(fontWeight: FontWeight.w700, fontSize: 16, color: ink)),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(
                  child: _QuickCard(Icons.shopping_bag_outlined, 'choice.marketplace_title'.tr(),
                      'choice.marketplace_subtitle'.tr(), () => context.push('/exchange')),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _QuickCard(Icons.trending_up_rounded, 'choice.mandi_title'.tr(), 'choice.mandi_subtitle'.tr(),
                      () => context.push('/markets')),
                ),
              ]),
              const SizedBox(height: 12),
              Row(children: [
                Expanded(
                  child: _QuickCard(Icons.health_and_safety_outlined, 'Crop Doctor / फसल निदान',
                      'Photo check for your crop', () => context.push('/crops')),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: _QuickCard(Icons.sensors_rounded, 'Farm Station', 'Live field readings', () => context.push('/station')),
                ),
              ]),
              const SizedBox(height: 32),
            ]),
          ),
        ),
      ),
    );
  }
}

class _TopIcon extends StatelessWidget {
  const _TopIcon(this.icon, this.color, this.onTap);

  final IconData icon;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => Container(
        decoration: BoxDecoration(
          color: glassFill(context.isDark),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: glassBorder(context.isDark)),
        ),
        child: IconButton(
          icon: Icon(icon, color: color, size: 20),
          onPressed: () {
            HapticFeedback.selectionClick();
            onTap();
          },
        ),
      );
}

class _ModeCard extends StatelessWidget {
  const _ModeCard({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => FarmCard(
        padding: const EdgeInsets.all(20),
        onTap: () {
          HapticFeedback.mediumImpact();
          onTap();
        },
        child: Row(children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.06), borderRadius: BorderRadius.circular(12)),
            child: Icon(icon, color: iconColor, size: 28),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: inkColor(context))),
              const SizedBox(height: 4),
              Text(subtitle, style: TextStyle(fontSize: 12, color: mutedColor(context))),
            ]),
          ),
          Icon(Icons.chevron_right_rounded, color: mutedColor(context)),
        ]),
      );
}

class _QuickCard extends StatelessWidget {
  const _QuickCard(this.icon, this.title, this.subtitle, this.onTap);

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => FarmCard(
        padding: const EdgeInsets.all(12),
        onTap: onTap,
        child: SizedBox(
          height: 96,
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.06), borderRadius: BorderRadius.circular(10)),
              child: Icon(icon, color: const Color(0xFF2E7D32), size: 20),
            ),
            const SizedBox(height: 8),
            Text(title,
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13, color: inkColor(context))),
            Text(subtitle,
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 10, color: mutedColor(context))),
          ]),
        ),
      );
}
