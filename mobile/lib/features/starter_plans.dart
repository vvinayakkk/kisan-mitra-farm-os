import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../assistant/assistant_controller.dart';
import '../ui/kit.dart';

const starterRoutines = <(IconData, String, String)>[
  (
    Icons.wb_sunny_outlined,
    'My morning farm walk',
    'Check the local forecast. Walk the field and note changes. Review today’s work with Mitra.'
  ),
  (
    Icons.eco_outlined,
    'Keep an eye on my crops',
    'Photograph a few representative leaves. Record growth or visible damage. Ask for help when something looks unusual.'
  ),
  (
    Icons.menu_book_outlined,
    'A simple money notebook',
    'Record farm expenses. Add sales and payments received. Review the week’s records.'
  ),
];

class StarterPlans extends ConsumerWidget {
  const StarterPlans({super.key, this.compact = false});
  final bool compact;
  @override
  Widget build(BuildContext context, WidgetRef ref) =>
      Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const SectionTitle('A good place to begin',
            eyebrow: 'STARTER ROUTINES'),
        Text(
            'Suggestions to make your own. Review with Mitra before adding them to your plan.',
            style: TextStyle(color: mutedColor(context), height: 1.5)),
        const SizedBox(height: 12),
        for (final (icon, title, detail) in starterRoutines)
          Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: FarmCard(
                onTap: compact
                    ? null
                    : () {
                        context.push('/chat');
                        ref.read(assistantProvider.notifier).send(
                            'Help me customise this starter routine for my farm: $title. $detail Ask for any missing farm details, then show the plan for my approval before saving.');
                      },
                child: Row(children: [
                  Icon(icon, color: accentColor(context)),
                  const SizedBox(width: 14),
                  Expanded(
                      child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                        Text(title,
                            style:
                                const TextStyle(fontWeight: FontWeight.w600)),
                        const SizedBox(height: 4),
                        Text(detail,
                            style: TextStyle(
                                fontSize: 12,
                                height: 1.5,
                                color: mutedColor(context))),
                      ])),
                  if (!compact)
                    const Icon(Icons.arrow_outward_rounded, size: 18)
                ]),
              )),
      ]);
}
