import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/api.dart';
import '../../core/session.dart';
import '../../core/workspace_cache.dart';
import '../../ui/form_sheet.dart';
import '../../ui/kit.dart';
import '../../ui/loader.dart';
import '../../utils/constants.dart';
import '../saathi.dart';
import 'exchange_mitra.dart';

const kExchangeCategories = {'equipment': 'Equipment', 'labour': 'Helping hands', 'transport': 'Transport', 'produce': 'Harvest'};
const kThreadStatus = {
  'open': 'Connected',
  'negotiating': 'Discussing terms',
  'agreed': 'Both agreed',
  'handover': 'Handover confirmed',
  'completed': 'Exchange complete',
  'cancelled': 'Closed',
  'disputed': 'Needs resolving',
};

/// Consenting farmers' resource notices, matches and private conversations.
/// Agreements and handovers are what participants report, not verified events.
class ExchangeScreen extends ConsumerStatefulWidget {
  const ExchangeScreen({super.key});

  @override
  ConsumerState<ExchangeScreen> createState() => _ExchangeScreenState();
}

class _ExchangeScreenState extends ConsumerState<ExchangeScreen> with SingleTickerProviderStateMixin {
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

  Future<void> _edit([Map<String, dynamic>? listing, Map<String, Object?>? draft]) async {
    final l = listing ?? draft ?? const {};
    final v = await showFormSheet(context,
        title: listing == null ? 'Share or request a resource' : 'Edit your notice',
        submit: 'Save notice',
        note: 'Published notices are visible to other farmers in this exchange, with your display name and district.',
        fields: [
          FieldSpec('kind', 'I am', kind: FieldKind.select, required: true, initial: l['kind'] ?? 'offer',
              options: const {'offer': 'Offering something', 'request': 'Looking for something'}),
          FieldSpec('category', 'Category', kind: FieldKind.select, required: true, initial: l['category'] ?? 'equipment', options: kExchangeCategories),
          FieldSpec('title', 'Title', required: true, initial: l['title'], maxLength: 160),
          FieldSpec('description', 'Description', kind: FieldKind.multiline, required: true, initial: l['description'], maxLength: 2000),
          FieldSpec('quantity', 'Quantity', kind: FieldKind.number, required: true, initial: l['quantity']),
          FieldSpec('unit', 'Unit', required: true, initial: l['unit'], maxLength: 40, help: 'e.g. days, quintals, people'),
          FieldSpec('state', 'State', required: true, initial: l['state'], maxLength: 100),
          FieldSpec('district', 'District', required: true, initial: l['district'], maxLength: 100),
          FieldSpec('available_on', 'Available from', kind: FieldKind.date, initial: l['available_on']),
          FieldSpec('exchange_for', 'In exchange for', initial: l['exchange_for'], maxLength: 500),
          FieldSpec('status', 'Visibility', kind: FieldKind.select, required: true, initial: listing?['status'] ?? 'draft',
              options: const {'draft': 'Draft (only you)', 'published': 'Published', 'withdrawn': 'Withdrawn'}),
          const FieldSpec('consent', 'I consent to publish this notice to other farmers', kind: FieldKind.check),
        ]);
    if (v == null || !mounted) return;
    if (v['status'] == 'published' && v['consent'] != true) {
      return showNotice(context, 'Publishing needs your consent.');
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
        await api.patch('/api/exchange/listings/${listing['id']}', body: {...body, 'row_version': listing['row_version']});
      }
      ref.read(workspaceCacheProvider).invalidate();
      if (mounted) showNotice(context, v['status'] == 'published' ? 'Notice published.' : 'Notice saved as ${v['status']}.');
    } on ApiException catch (e) {
      if (mounted) showNotice(context, e.message);
    }
    _browse.currentState?.reload();
    _mine.currentState?.reload();
  }

  Widget _list({required bool mine, required GlobalKey<LoaderState<Map<String, dynamic>>> key}) {
    final api = ref.read(apiProvider);
    return Loader<Map<String, dynamic>>(
      key: key,
      loading: 'Looking for resources…',
      load: () async => asMap(await api.get('/api/exchange/listings', query: {
        if (mine) 'mine': true,
        if (!mine && _category != null) 'category': _category,
        if (!mine && _query.text.trim().isNotEmpty) 'q': _query.text.trim(),
      })),
      builder: (context, d) {
        final items = asMaps(d['items']);
        return ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 96), children: [
          if (!mine) ...[
            const PreparedBySaathi(area: 'exchange'),
            TextField(
              controller: _query,
              decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search resources'),
              onChanged: (_) {
                _debounce?.cancel();
                _debounce = Timer(const Duration(milliseconds: 300), () => _browse.currentState?.reload());
              },
            ),
            const SizedBox(height: 8),
            Wrap(spacing: 6, runSpacing: 6, children: [
              OutlineChip(label: 'All', selected: _category == null, onTap: () {
                setState(() => _category = null);
                _browse.currentState?.reload();
              }),
              for (final e in kExchangeCategories.entries)
                OutlineChip(label: e.value, selected: _category == e.key, onTap: () {
                  setState(() => _category = e.key);
                  _browse.currentState?.reload();
                }),
            ]),
            const SizedBox(height: 8),
          ],
          if (items.isEmpty)
            EmptyView(
              title: mine ? 'Your resources belong here.' : 'No resources fit this search yet.',
              detail: mine ? 'Share equipment, labour, transport or harvest with nearby farmers.' : 'Be the first to share something useful.',
              action: FilledButton(onPressed: _edit, child: const Text('Create a notice')),
            ),
          for (final l in items) _ListingCard(listing: l, mine: mine, onEdit: () => _edit(l)),
          Text('Private coordination · no external messages. Distances are not computed; locations are district level.',
              style: TextStyle(fontSize: 11, color: mutedColor(context))),
        ]);
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    return Scaffold(
      appBar: AppBar(
        title: Text('Farmer exchange', style: TextStyle(color: ink)),
        foregroundColor: ink,
        actions: [
          IconButton(
            tooltip: 'Ask Mitra to draft',
            icon: const Icon(Icons.auto_awesome),
            onPressed: () => showExchangeMitra(context, intent: 'prepare_listing', onDraft: (d) {
              if (d['kind'] == 'listing') _edit(null, asMap(d['fields']));
            }),
          ),
        ],
        bottom: TabBar(
          controller: _tabs,
          labelColor: AppColors.primaryDark,
          unselectedLabelColor: mutedColor(context),
          tabs: const [Tab(text: 'Browse'), Tab(text: 'My notices'), Tab(text: 'Conversations')],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        heroTag: 'exchange-new',
        onPressed: _edit,
        icon: const Icon(Icons.add),
        label: const Text('New notice'),
      ),
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
  const _ListingCard({required this.listing, required this.mine, required this.onEdit});

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
              child: Text(l['kind'] == 'request' ? 'LOOKING FOR' : 'AVAILABLE TO SHARE',
                  style: const TextStyle(fontSize: 11, letterSpacing: 1, fontWeight: FontWeight.w700, color: AppColors.primaryDark)),
            ),
            if (sample) const Tag('Sample', color: AppColors.warning) else const Tag('Farmer reported', color: Color(0xFF7C3AED)),
            if (mine) ...[const SizedBox(width: 6), Tag(str(l['status']))],
          ]),
          Text(str(l['title']), style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: ink)),
          Text('${kExchangeCategories[l['category']] ?? ''} · ${l['quantity']} ${str(l['unit'])} · ${str(l['district'])}, ${str(l['state'])}',
              style: TextStyle(fontSize: 12.5, color: mutedColor(context))),
          if (!mine) Text(str(l['owner_name'], str(l['display_name'], 'Member listing')), style: TextStyle(fontSize: 12, color: mutedColor(context))),
          if (str(l['exchange_for']).isNotEmpty) Text('In exchange for: ${l['exchange_for']}', style: TextStyle(color: ink)),
          if (mine && l['status'] == 'published')
            TextButton(onPressed: () => _showMatches(context, ref, l), child: const Text('See matching notices')),
        ]),
      ),
    );
  }

  void _showListing(BuildContext context, WidgetRef ref, Map<String, dynamic> l) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (c) => Padding(
        padding: const EdgeInsets.all(16),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(str(l['title']), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          const SizedBox(height: 6),
          Text(str(l['description'])),
          const SizedBox(height: 6),
          Text('${l['quantity']} ${str(l['unit'])} · ${str(l['district'])}, ${str(l['state'])}'
              '${l['available_on'] != null ? ' · from ${displayDate(str(l['available_on']))}' : ''}'),
          const SizedBox(height: 12),
          const Text('Starting a conversation shares your display name with this farmer. No message leaves the app.',
              style: TextStyle(fontSize: 12)),
          const SizedBox(height: 8),
          FilledButton.icon(
            onPressed: () async {
              try {
                final t = asMap(await ref.read(apiProvider).post('/api/exchange/conversations',
                    body: {'listing_id': l['id'], 'consent_to_share_display_name': true}));
                if (c.mounted) Navigator.pop(c);
                if (context.mounted) context.push('/exchange/thread/${t['id']}');
              } on ApiException catch (e) {
                if (c.mounted) showNotice(c, e.message);
              }
            },
            icon: const Icon(Icons.forum_outlined),
            label: const Text('Discuss exchange'),
          ),
        ]),
      ),
    );
  }

  void _showMatches(BuildContext context, WidgetRef ref, Map<String, dynamic> l) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (c) => SizedBox(
        height: MediaQuery.sizeOf(c).height * 0.7,
        child: Loader<Map<String, dynamic>>(
          loading: 'Comparing resource matches…',
          load: () async => asMap(await ref.read(apiProvider).get('/api/exchange/matches', query: {'listing_id': l['id']})),
          builder: (c, d) {
            final items = asMaps(d['items']);
            return ListView(padding: const EdgeInsets.all(12), children: [
              Text('Matches for “${l['title']}”', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
              if (str(d['note']).isNotEmpty) Text(str(d['note']), style: const TextStyle(fontSize: 12)),
              if (items.isEmpty) const EmptyView(title: 'No available match yet.'),
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
    _poll = Timer.periodic(const Duration(seconds: 12), (_) => _loader.currentState?.reload());
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Loader<Map<String, dynamic>>(
        key: _loader,
        loading: 'Loading conversations…',
        load: () async => asMap(await ref.read(apiProvider).get('/api/exchange/conversations')),
        builder: (context, d) {
          final items = asMaps(d['items']);
          if (items.isEmpty) {
            return ListView(children: const [EmptyView(title: 'A useful conversation starts with a resource.')]);
          }
          return ListView(padding: const EdgeInsets.all(12), children: [
            for (final t in items)
              Card(
                child: ListTile(
                  title: Text(str(t['listing_title'], 'Exchange')),
                  subtitle: Text('${kThreadStatus[t['status']] ?? str(t['status'])} · '
                      '${asMaps(t['participants']).map((p) => str(p['display_name'])).join(' & ')}'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => context.push('/exchange/thread/${t['id']}'),
                ),
              ),
          ]);
        },
      );
}
