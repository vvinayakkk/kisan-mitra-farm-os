import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../assistant/assistant_controller.dart';
import '../assistant/chat_screen.dart';
import '../ui/kit.dart';
import 'calendar_screen.dart';
import 'station_screen.dart';

/// Phone layout of Farm OS: Assistant, Calendar and Farm station stay one tap
/// away (as in the web header); everything else lives under "Farm".
class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});

  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final pending = ref.watch(assistantProvider.select((s) => s.pending != null && !s.busy));
    return Scaffold(
      body: IndexedStack(index: _index, children: const [ChatScreen(), CalendarScreen(), StationScreen(), _FarmMenu()]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: [
          NavigationDestination(
            icon: Badge(isLabelVisible: pending && _index != 0, label: const Text('1'), child: const Icon(Icons.chat_bubble_outline)),
            selectedIcon: const Icon(Icons.chat_bubble),
            label: 'Assistant',
          ),
          const NavigationDestination(icon: Icon(Icons.calendar_month_outlined), selectedIcon: Icon(Icons.calendar_month), label: 'Calendar'),
          const NavigationDestination(icon: Icon(Icons.sensors_outlined), selectedIcon: Icon(Icons.sensors), label: 'Station'),
          const NavigationDestination(icon: Icon(Icons.grid_view_outlined), selectedIcon: Icon(Icons.grid_view), label: 'Farm'),
        ],
      ),
    );
  }
}

class _FarmMenu extends StatelessWidget {
  const _FarmMenu();

  static const _items = <(String, String, IconData, Color, String)>[
    ('Farm weather', 'Today, next hours and the days ahead', Icons.cloud_outlined, Color(0xFF0EA5E9), '/weather'),
    ('Crop Doctor', 'A careful check for your crops', Icons.healing_rounded, Color(0xFF10B981), '/crops'),
    ('Market prices', 'Dated prices, clearer choices', Icons.storefront_outlined, Color(0xFFF59E0B), '/markets'),
    ('Farm support', 'Benefits and application checklists', Icons.account_balance_outlined, Color(0xFF9C27B0), '/schemes'),
    ('Farm notebook', 'Your files, plans and saved costs', Icons.menu_book_outlined, Color(0xFF795548), '/notebook'),
    ('Farmer exchange', 'Find a resource, agree together', Icons.handshake_outlined, Color(0xFF00BCD4), '/exchange'),
    ('Saathi', 'Prepared suggestions and follow-ups', Icons.spa_outlined, Color(0xFF16A34A), '/saathi'),
    ('My farm profile', 'Identity, language and farm details', Icons.person_outlined, Color(0xFFFF5722), '/profile'),
  ];

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    return Scaffold(
      appBar: AppBar(title: Text('Your farm', style: TextStyle(color: ink)), foregroundColor: ink),
      body: FarmBackground(
        child: SizedBox.expand(child: LayoutBuilder(builder: (context, c) {
          // Intrinsic-height tiles: large system fonts grow the tile instead of overflowing.
          final columns = c.maxWidth >= 600 ? 3 : 2;
          final width = (c.maxWidth - 24 - 10 * (columns - 1)) / columns;
          return SingleChildScrollView(
            padding: const EdgeInsets.all(12),
            physics: const AlwaysScrollableScrollPhysics(),
            child: Wrap(spacing: 10, runSpacing: 10, children: [
              for (final (title, caption, icon, color, route) in _items)
                SizedBox(
                  width: width,
                  child: FarmCard(
                    onTap: () => context.push(route),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      CircleAvatar(backgroundColor: color.withValues(alpha: 0.15), child: Icon(icon, color: color)),
                      const SizedBox(height: 10),
                      Text(title, style: TextStyle(fontWeight: FontWeight.w700, color: ink)),
                      const SizedBox(height: 2),
                      Text(caption, style: TextStyle(fontSize: 12, color: mutedColor(context))),
                    ]),
                  ),
                ),
            ]),
          );
        })),
      ),
    );
  }
}
