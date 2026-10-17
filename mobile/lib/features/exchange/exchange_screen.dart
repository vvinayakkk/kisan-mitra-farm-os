import '../../tour/app_tour.dart';
import 'package:easy_localization/easy_localization.dart';
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api.dart';
import '../../core/session.dart';
import '../../core/workspace_cache.dart';
import '../../ui/form_sheet.dart';
import '../../ui/kit.dart';
import '../../ui/labels.dart';
import '../../ui/loader.dart';
import '../../utils/constants.dart';
import '../saathi.dart';
import 'exchange_mitra.dart';

const kExchangeCategories = {
  'equipment': 'fos.market.cat_equipment',
  'labour': 'fos.market.cat_labour',
  'transport': 'fos.market.cat_transport',
  'produce': 'fos.market.cat_produce',
};
const kThreadStatus = {
  'open': 'fos.market.st_open',
  'negotiating': 'fos.market.st_negotiating',
  'agreed': 'fos.market.st_agreed',
  'handover': 'fos.market.st_handover',
  'completed': 'fos.market.st_completed',
  'cancelled': 'fos.market.st_cancelled',
  'disputed': 'fos.market.st_disputed',
};

/// Consenting farmers' resource notices, matches and private conversations.
/// Agreements and handovers are what participants report, not verified events.
class ExchangeScreen extends ConsumerStatefulWidget {
  const ExchangeScreen({super.key});

  @override
  ConsumerState<ExchangeScreen> createState() => _ExchangeScreenState();
}

class _ExchangeScreenState extends ConsumerState<ExchangeScreen>
    with SingleTickerProviderStateMixin {
  late final _tabs = TabController(length: 3, vsync: this);
  final _browse = GlobalKey<LoaderState<Map<String, dynamic>>>();
  final _mine = GlobalKey<LoaderState<Map<String, dynamic>>>();
  String? _category;
  final _query = TextEditingController();
  Timer? _debounce;

  @override
  void dispose() {
    _tabs.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  Future<void> _edit(
      [Map<String, dynamic>? listing, Map<String, Object?>? draft]) async {
    final l = listing ?? draft ?? const {};
    final v = await showFormSheet(context,
        title: listing == null
            ? 'fos.market.new_notice'.tr()
            : 'fos.market.edit_notice'.tr(),
        submit: 'fos.market.save'.tr(),
        note: 'fos.market.publish_note'.tr(),
        fields: [
          FieldSpec('kind', 'fos.market.i_am'.tr(),
              kind: FieldKind.select,
              required: true,
              initial: l['kind'] ?? 'offer',
              options: {
                'offer': 'fos.market.offering'.tr(),
                'request': 'fos.market.looking_for'.tr()
              }),
          FieldSpec('category', 'fos.market.category'.tr(),
              kind: FieldKind.select,
              required: true,
              initial: l['category'] ?? 'equipment',
              options: {
                for (final c in kExchangeCategories.entries) c.key: c.value.tr()
              }),
          FieldSpec('title', 'fos.market.f_title'.tr(),
              required: true, initial: l['title'], maxLength: 160),
          FieldSpec('description', 'fos.market.f_description'.tr(),
              kind: FieldKind.multiline,
              required: true,
              initial: l['description'],
              maxLength: 2000),
          FieldSpec('quantity', 'fos.market.f_quantity'.tr(),
              kind: FieldKind.number, required: true, initial: l['quantity']),
          FieldSpec('unit', 'fos.market.f_unit'.tr(),
              required: true,
              initial: l['unit'],
              maxLength: 40,
              help: 'fos.market.unit_help'.tr()),
          FieldSpec('state', 'fos.market.f_state'.tr(),
              required: true, initial: l['state'], maxLength: 100),
          FieldSpec('district', 'fos.market.district'.tr(),
              required: true, initial: l['district'], maxLength: 100),
          FieldSpec('available_on', 'fos.market.available_from'.tr(),
              kind: FieldKind.date, initial: l['available_on']),
          FieldSpec('exchange_for', 'fos.market.in_exchange'.tr(),
              initial: l['exchange_for'], maxLength: 500),
          FieldSpec('status', 'fos.market.visibility'.tr(),
              kind: FieldKind.select,
              required: true,
              initial: listing?['status'] ?? 'draft',
              options: {
                'draft': 'fos.market.vis_draft'.tr(),
                'published': 'fos.market.vis_published'.tr(),
                'withdrawn': 'fos.market.vis_withdrawn'.tr()
              }),
          FieldSpec('consent', 'fos.market.consent'.tr(),
              kind: FieldKind.check),
        ]);
    if (v == null || !mounted) return;
    if (v['status'] == 'published' && v['consent'] != true) {
      return showNotice(context, 'fos.market.consent_needed'.tr());
    }
    final body = {
      for (final e in v.entries)
        if (e.key != 'consent') e.key: e.value,
      'exchange_for': v['exchange_for'] ?? '',
      'consent_to_publish': v['consent'] == true,
    };
    try {
      final api = ref.read(apiProvider);
      if (listing == null) {
        await api.post('/api/exchange/listings', body: body);
      } else {
        await api.patch('/api/exchange/listings/${listing['id']}',
            body: {...body, 'row_version': listing['row_version']});
      }
      ref.read(workspaceCacheProvider).invalidate();
      if (mounted) {
        showNotice(
            context,
            v['status'] == 'published'
                ? 'fos.market.published'.tr()
                : 'fos.market.saved_dot'.tr());
      }
    } on ApiException catch (e) {
      if (mounted) showNotice(context, e.message);
    }
    _browse.currentState?.reload();
    _mine.currentState?.reload();
  }

  Widget _list(
      {required bool mine,
      required GlobalKey<LoaderState<Map<String, dynamic>>> key}) {
    final api = ref.read(apiProvider);
    return Loader<Map<String, dynamic>>(
      key: key,
      loading: 'fos.market.loading'.tr(),
      load: () async => asMap(await api.get('/api/exchange/listings', query: {
        if (mine) 'mine': true,
        if (!mine && _category != null) 'category': _category,
        if (!mine && _query.text.trim().isNotEmpty) 'q': _query.text.trim(),
      })),
      builder: (context, d) {
        final items = asMaps(d['items']);
        return ListView(
            padding: const EdgeInsets.fromLTRB(24, 8, 24, 96),
            children: [
              if (!mine) ...[
                const FeatureIntro(
                    eyebrow: 'YOUR FARMING COMMUNITY',
                    title: 'Better, together.',
                    detail:
                        'Find equipment, share resources and work with farmers around you.',
                    icon: Icons.handshake_outlined),

                const PreparedBySaathi(area: 'exchange'),
                TextField(
                  controller: _query,
                  decoration: InputDecoration(
                      prefixIcon: const Icon(Icons.search),
                      hintText: 'fos.market.search_resources'.tr()),
                  onChanged: (_) {
                    _debounce?.cancel();
                    _debounce = Timer(const Duration(milliseconds: 300),
                        () => _browse.currentState?.reload());
                  },
                ),
                const SizedBox(height: 8),
                Wrap(spacing: 6, runSpacing: 6, children: [
                  OutlineChip(
                      label: 'fos.market.all'.tr(),
                      selected: _category == null,
                      onTap: () {
                        HapticFeedback.selectionClick();
                        setState(() => _category = null);
                        _browse.currentState?.reload();
                      }),
                  for (final e in kExchangeCategories.entries)
                    OutlineChip(
                        label: e.value.tr(),
                        selected: _category == e.key,
                        onTap: () {
                          HapticFeedback.selectionClick();
                          setState(() => _category = e.key);
                          _browse.currentState?.reload();
                        }),
                ]),
                const SizedBox(height: 8),
              ],
              if (items.isEmpty)
                EmptyView(
                  title: mine
                      ? 'fos.market.no_notices'.tr()
                      : 'fos.market.nothing_found'.tr(),
                  action: FilledButton.tonal(
                      onPressed: _edit,
                      child: Text('fos.market.new_notice'.tr())),
                ),
              for (final l in items)
                _ListingCard(listing: l, mine: mine, onEdit: () => _edit(l)),
            ]);
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('fos.market.farmer_exchange'.tr()),
        actions: [
          const TourReplayButton(),
          TourAnchor(id: 'exchange-mitra', child: IconButton(
            tooltip: 'fos.market.ask_mitra_draft'.tr(),
            icon: const Icon(Icons.auto_awesome),
            onPressed: () => showExchangeMitra(context,
                intent: 'prepare_listing', onDraft: (d) {
              if (d['kind'] == 'listing') _edit(null, asMap(d['fields']));
            }),
          )),
        ],
        bottom: TabBar(
          controller: _tabs,
          labelColor: AppColors.primaryDark,
          unselectedLabelColor: mutedColor(context),
          tabs: [
            Tab(text: 'fos.market.tab_browse'.tr()),
            Tab(text: 'fos.market.tab_mine'.tr()),
            TourAnchor(id: 'exchange-tabs', child: Tab(text: 'fos.market.tab_chats'.tr()))
          ],
        ),
      ),
      floatingActionButton: TourAnchor(id: 'exchange-new', child: FloatingActionButton.extended(
        heroTag: 'exchange-new',
        onPressed: _edit,
        icon: const Icon(Icons.add),
        label: Text('fos.market.new'.tr()),
      )),
      body: FarmBackground(
        child: TabBarView(controller: _tabs, children: [
          _list(mine: false, key: _browse),
          _list(mine: true, key: _mine),
          const _Inbox(),
        ]),
      ),
    );
  }
}

class _ListingCard extends ConsumerWidget {
  const _ListingCard(
      {required this.listing, required this.mine, required this.onEdit});

  final Map<String, dynamic> listing;
  final bool mine;
  final VoidCallback onEdit;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ink = inkColor(context);
    final l = listing;
    final sample = l['data_origin'] == 'synthetic';
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: FarmCard(
        onTap: mine ? onEdit : () => _showListing(context, ref, l),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Text(
                  (l['kind'] == 'request'
                          ? 'fos.market2.needed'
                          : 'fos.market2.available_offer')
                      .tr(),
                  style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w700,
                      color: context.isDark
                          ? AppColors.primaryLight
                          : AppColors.primaryDark)),
            ),
            if (sample)
              const Tooltip(message: 'Reference listing from the local dataset', child: Icon(Icons.info_outline, size: 16))
            else
              Tag('fos.market.farmer_reported'.tr(),
                  color: context.isDark
                      ? const Color(0xFFA78BFA)
                      : const Color(0xFF7C3AED)),
            if (mine) ...[
              const SizedBox(width: 6),
              Tag(const {
                    'draft': 'fos.market.vis_draft',
                    'published': 'fos.market.vis_published',
                    'withdrawn': 'fos.market.vis_withdrawn'
                  }[l['status']]
                      ?.tr() ??
                  statusLabel(l['status']))
            ],
          ]),
          const SizedBox(height: 2),
          Text(str(l['title']),
              style: TextStyle(
                  fontSize: 16, fontWeight: FontWeight.w700, color: ink)),
          const SizedBox(height: 4),
          Text(
              str(l['exchange_for']).isNotEmpty
                  ? 'fos.market2.in_exchange_for'
                      .tr(namedArgs: {'text': str(l['exchange_for'])})
                  : 'fos.market2.terms_talk'.tr(),
              style: TextStyle(
                  fontSize: 15, fontWeight: FontWeight.w600, color: ink)),
          const SizedBox(height: 4),
          Text(
              '${_category(l['category'])} · ${qty(l['quantity'])} ${str(l['unit'])}'
                  .trim(),
              style: TextStyle(fontSize: 13, color: mutedColor(context))),
          Text(_place(l),
              style: TextStyle(fontSize: 13, color: mutedColor(context))),
          if (!mine)
            Text(
                str(l['owner_name'],
                    str(l['display_name'], 'fos.market.member_listing'.tr())),
                style: TextStyle(fontSize: 13, color: mutedColor(context))),
          if (mine && l['status'] == 'published')
            FilledButton.tonal(
                onPressed: () => _showMatches(context, ref, l),
                child: Text('fos.market.matches'.tr())),
        ]),
      ),
    );
  }

  void _showListing(
      BuildContext context, WidgetRef ref, Map<String, dynamic> l) {
    final swap = str(l['exchange_for']).isNotEmpty
        ? 'fos.market2.in_exchange_for'
            .tr(namedArgs: {'text': str(l['exchange_for'])})
        : 'fos.market2.terms_talk'.tr();
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (c) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(str(l['title']),
                  style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: inkColor(c))),
              const SizedBox(height: 6),
              Text(str(l['description']), style: TextStyle(color: inkColor(c))),
              const SizedBox(height: 6),
              Text(swap,
                  style: TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: inkColor(c))),
              const SizedBox(height: 6),
              Text(
                  '${qty(l['quantity'])} ${str(l['unit'])} · ${_place(l)}'
                  '${l['available_on'] != null ? ' · ${'fos.market.from_date'.tr(namedArgs: {
                          'date': displayDate(str(l['available_on']))
                        })}' : ''}',
                  style: TextStyle(color: inkColor(c))),
              const SizedBox(height: 12),
              Text('fos.market.chat_shares_name'.tr(),
                  style: TextStyle(fontSize: 13, color: mutedColor(c))),
              const SizedBox(height: 8),
              FilledButton.icon(
                onPressed: () async {
                  HapticFeedback.selectionClick();
                  try {
                    final t = asMap(await ref
                        .read(apiProvider)
                        .post('/api/exchange/conversations', body: {
                      'listing_id': l['id'],
                      'consent_to_share_display_name': true
                    }));
                    if (c.mounted) Navigator.pop(c);
                    if (context.mounted) {
                      context.push('/exchange/thread/${t['id']}');
                    }
                  } on ApiException catch (e) {
                    if (c.mounted) showNotice(c, e.message);
                  }
                },
                icon: const Icon(Icons.forum_outlined),
                label: Text('fos.market.discuss'.tr()),
              ),
            ]),
      ),
    );
  }

  String _category(Object? c) =>
      kExchangeCategories[c]?.tr() ?? humanize('${c ?? ''}');

  String _place(Map<String, dynamic> l) => [l['district'], l['state']]
      .where((e) => str(e).isNotEmpty)
      .map(phrase)
      .join(', ');

  void _showMatches(
      BuildContext context, WidgetRef ref, Map<String, dynamic> l) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (c) => SizedBox(
        height: MediaQuery.sizeOf(c).height * 0.7,
        child: Loader<Map<String, dynamic>>(
          loading: 'fos.market.loading'.tr(),
          load: () async => asMap(await ref
              .read(apiProvider)
              .get('/api/exchange/matches', query: {'listing_id': l['id']})),
          builder: (c, d) {
            final items = asMaps(d['items']);
            return ListView(padding: const EdgeInsets.all(12), children: [
              Text(
                  'fos.market.matches_for'
                      .tr(namedArgs: {'title': '${l['title']}'}),
                  style: TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 16,
                      color: inkColor(c))),
              if (items.isEmpty) EmptyView(title: 'fos.market.no_match'.tr()),
              for (final m in items)
                _ListingCard(listing: m, mine: false, onEdit: () {}),
            ]);
          },
        ),
      ),
    );
  }
}

class _Inbox extends ConsumerStatefulWidget {
  const _Inbox();

  @override
  ConsumerState<_Inbox> createState() => _InboxState();
}

class _InboxState extends ConsumerState<_Inbox> {
  final _loader = GlobalKey<LoaderState<Map<String, dynamic>>>();
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _poll = Timer.periodic(
        const Duration(seconds: 12), (_) => _loader.currentState?.reload());
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Loader<Map<String, dynamic>>(
        key: _loader,
        loading: 'fos.market.loading'.tr(),
        load: () async => asMap(
            await ref.read(apiProvider).get('/api/exchange/conversations')),
        builder: (context, d) {
          final items = asMaps(d['items']);
          if (items.isEmpty) {
            return ListView(
                children: [EmptyView(title: 'fos.market.no_chats'.tr())]);
          }
          return ListView(padding: const EdgeInsets.all(12), children: [
            for (final t in items)
              Card(
                child: ListTile(
                  title:
                      Text(str(t['listing_title'], 'fos.market.exchange'.tr())),
                  subtitle: Text(
                      '${kThreadStatus[t['status']]?.tr() ?? statusLabel(t['status'])} · '
                      '${asMaps(t['participants']).map((p) => str(p['display_name'])).join(' & ')}'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('/exchange/thread/${t['id']}'),
                ),
              ),
          ]);
        },
      );
}
