import '../tour/app_tour.dart';
import 'package:easy_localization/easy_localization.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../assistant/helper_sheet.dart';
import '../assistant/widgets/farm_result.dart';
import '../core/api.dart';
import '../core/session.dart';
import '../core/workspace_cache.dart';
import '../ui/kit.dart';
import '../ui/labels.dart';
import '../ui/loader.dart';
import '../ui/provenance.dart';
import '../utils/constants.dart';
import 'workspace_tools.dart';

/// Dated mandi observations and their history. Prices are records, not offers;
/// the take-home figures are the farmer's own estimate.
class MarketsScreen extends ConsumerStatefulWidget {
  const MarketsScreen({super.key});

  @override
  ConsumerState<MarketsScreen> createState() => _MarketsScreenState();
}

class _MarketsScreenState extends ConsumerState<MarketsScreen> {
  final _crop = TextEditingController(text: 'Wheat');
  final _state = TextEditingController();
  String? _market;
  bool _showSearch = false;
  Map<String, dynamic>? _prices;
  Map<String, dynamic>? _trend;
  Map<String, dynamic> _catalogue = const {};
  String? _error;
  bool _busy = false;
  int _shown = 9, _searchGeneration = 0;
  String? _queryKey;
  List<String> _myCrops = const [];
  final _compare = <Map<String, dynamic>>[];

  @override
  void initState() {
    super.initState();
    _loadCatalogue();
    _init();
  }

  Future<void> _init() async {
    // Start from the farmer's own first crop and state.
    try {
      final p = asMap(asMap(await ref.read(apiProvider).get('/api/profile'))['profile']);
      _myCrops = (p['crops'] as List? ?? const []).map((e) => '$e'.trim()).where((e) => e.isNotEmpty).toList();
      if (_myCrops.isNotEmpty) _crop.text = _myCrops.first;
      if (str(p['state']).isNotEmpty) _state.text = str(p['state']);
    } catch (_) {
      // Profile is optional; defaults stay.
    }
    if (mounted) {
      setState(() {});
      _search();
    }
  }

  Future<void> _loadCatalogue() async {
    try {
      final data = await ref.cachedGet('/api/mandi/catalogue', query: {'limit': 200});
      if (mounted) setState(() => _catalogue = asMap(data));
    } catch (_) {
      // Directory suggestions are optional; search still works.
    }
  }

  String get _today => isoDate(DateTime.now().toUtc().add(const Duration(hours: 5, minutes: 30)));

  Future<void> _search({String? market}) async {
    final crop = _crop.text.trim();
    if (crop.isEmpty) return;
    _market = market;
    setState(() {
      _busy = true;
      _error = null;
      _shown = 9;
    });
    final tools = ref.read(workspaceToolsProvider);
    final args = {'commodity': crop, 'state': _state.text.trim(), 'observed_only': ref.read(authProvider).mode != BackendMode.demo, if (market != null) 'market': market};
    final generation = ++_searchGeneration;
    final key = args.toString();
    if (_queryKey != key) {
      setState(() { _prices = null; _trend = null; _queryKey = key; });
    }
    // Prices become usable as soon as they arrive; trend is supplementary.
    final prices = tools.inspect('market_prices', args).then((value) {
      if (mounted && generation == _searchGeneration) {
        setState(() { _prices = value; _busy = false; });
      }
    }, onError: (Object e) {
      if (mounted && generation == _searchGeneration) {
        setState(() { _busy = false; _error = e is ApiException ? e.message : 'fos.market.prices_load_failed'.tr(); });
      }
    });
    final trend = tools.inspect('market_trend', args).then((value) {
      if (mounted && generation == _searchGeneration) setState(() => _trend = value);
    }, onError: (Object _) {});
    await Future.wait([prices, trend]);
  }

  void _calculate(List<Map<String, dynamic>> rows) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (c) => _TakeHome(
          rows: rows,
          onClear: () {
            setState(_compare.clear);
            Navigator.pop(c);
          }),
    );
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    final rows = asMaps(_prices?['rates'] ?? _prices?['records'])
        .where((r) => str(r['arrival_date']).compareTo(_today) <= 0 || str(r['arrival_date']).isEmpty)
        .toList();
    final markets = asMaps(_catalogue['markets']).take(12).toList();
    return Scaffold(
      appBar: AppBar(actions: const [TourReplayButton()], title: Text('fos.market.title'.tr())),
      floatingActionButton: const HelperButton(contextKey: 'markets'),
      body: FarmBackground(
        child: ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 96), children: [

          if (rows.isNotEmpty) Padding(padding: const EdgeInsets.only(bottom: 16), child: FarmCard(color: context.isDark ? AppColors.darkCard : const Color(0xFFF0EEE7), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('PREPARED BY MITRA', style: TextStyle(fontSize: 10, letterSpacing: 1.3, fontWeight: FontWeight.w600, color: accentColor(context))),
            const SizedBox(height: 8), Text('Let’s compare your ${cropName(_crop.text.trim())}.', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
            const SizedBox(height: 8), Text('${rows.length} dated records are ready. Compare matching grades and units, then include transport and market fees.', style: const TextStyle(fontSize: 13, height: 1.5)),
            TourAnchor(id: 'comparison', child: TextButton.icon(onPressed: () => _calculate(rows.take(3).toList()), icon: const Icon(Icons.calculate_outlined, size: 18), label: const Text('Compare what I take home'))),
          ]))),
          if (_myCrops.isNotEmpty) ...[
            Text('fos.market2.your_crops'.tr(),
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: ink)),
            const SizedBox(height: 6),
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (final c in _myCrops)
                OutlineChip(
                  label: cropName(c),
                  selected: _crop.text.trim().toLowerCase() == c.toLowerCase(),
                  onTap: () {
                    HapticFeedback.selectionClick();
                    _crop.text = c;
                    _search();
                  },
                ),
            ]),
            const SizedBox(height: 8),
          ],
          // Farmer's own crop and state are searched automatically; manual
          // search stays one tap away.
          Align(
            alignment: Alignment.centerRight,
            child: TourAnchor(id: 'market-search', child: TextButton.icon(
              onPressed: () => setState(() => _showSearch = !_showSearch),
              icon: Icon(_showSearch ? Icons.expand_less : Icons.search, size: 18),
              label: Text((_showSearch ? 'fos.label.hide_search' : 'fos.label.other_crop').tr()),
            )),
          ),
          if (_showSearch)
            FarmCard(
              child: Column(children: [
                _Suggest(
                    controller: _crop,
                    label: 'fos.market.crop'.tr(),
                    options: (_catalogue['commodities'] as List? ?? const []).map((e) => '$e').toList()),
                const SizedBox(height: 8),
                _Suggest(
                    controller: _state,
                    label: 'fos.market.state_optional'.tr(),
                    options: (_catalogue['states'] as List? ?? const []).map((e) => '$e').toList()),
                const SizedBox(height: 8),
                Row(children: [
                  if (_market != null) Expanded(child: InputChip(label: Text(_market!), onDeleted: () => _search())),
                  const Spacer(),
                  FilledButton.icon(
                    onPressed: _busy
                        ? null
                        : () {
                            HapticFeedback.selectionClick();
                            _search(market: _market);
                          },
                    icon: const Icon(Icons.search),
                    label: Text('fos.market.look_up'.tr()),
                  ),
                ]),
              ]),
            ),
          if (_busy) LoadingView('fos.market.loading'.tr()),
          if (_error != null) ErrorView(_error!, onRetry: () => _search(market: _market)),
          if (!_busy && _prices != null) ...[
            SectionTitle(cropName(_crop.text.trim()), trailing: ProvenanceBadge.maybe(_prices!['provenance'])),
            Text(
                'fos.market.source_line'
                    .tr(namedArgs: {'source': phrase(str(_prices!['source'], 'fos.market.mandi_prices'.tr()))}),
                style: TextStyle(fontSize: 13, color: mutedColor(context))),
            const SizedBox(height: 6),
            if (rows.isEmpty)
              EmptyView(
                title: 'fos.market.no_prices'.tr(),
                detail: str(_prices!['message']).isEmpty ? null : str(_prices!['message']),
              )
            else ...[
              for (final r in rows.take(_shown))
                _PriceCard(
                    row: r,
                    onHistory: () => _search(market: str(r['market'])),
                    onCompare: () {
                      setState(() {
                        if (_compare.length >= 3) _compare.removeAt(0);
                        _compare.add(r);
                      });
                    }),
              if (rows.length > _shown)
                TextButton(onPressed: () => setState(() => _shown += 9), child: Text('fos.market.more'.tr())),
            ],
            if (rows.isNotEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: FilledButton.icon(
                  onPressed: () => _calculate(_compare.isNotEmpty ? List.of(_compare) : rows.take(3).toList()),
                  icon: const Icon(Icons.calculate_outlined),
                  label: Text('fos.market2.calc_button'.tr()),
                ),
              ),
            SectionTitle('fos.market.trend'.tr()),
            if (_trend != null && ChartData.tryParse(_trend!['chart']) != null)
              FarmResult(_trend!)
            else
              Text('fos.market.no_trend'.tr(), style: TextStyle(color: mutedColor(context))),
            if (markets.isNotEmpty)
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: Text('fos.market.directory'.tr(namedArgs: {'count': '${markets.length}'}),
                    style: TextStyle(color: ink)),
                children: [
                  for (final m in markets)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(str(m['name'])),
                      subtitle: Text([m['district'], m['state']].where((e) => e != null).map(phrase).join(', ')),
                      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                        if (str(m['source_url']).startsWith('https://'))
                          IconButton(
                            tooltip: 'fos.market.source'.tr(),
                            icon: const Icon(Icons.open_in_new, size: 18),
                            onPressed: () =>
                                launchUrl(Uri.parse(str(m['source_url'])), mode: LaunchMode.externalApplication),
                          ),
                        TextButton(
                            onPressed: () => _search(market: str(m['name'])), child: Text('fos.market.select'.tr())),
                      ]),
                    ),
                ],
              ),
            TextButton.icon(
              onPressed: () => context.push('/exchange'),
              icon: const Icon(Icons.handshake_outlined),
              label: Text('fos.market.farmer_exchange'.tr()),
            ),
          ],
        ]),
      ),
    );
  }
}

class _PriceCard extends StatelessWidget {
  const _PriceCard({required this.row, required this.onHistory, required this.onCompare});

  final Map<String, dynamic> row;
  final VoidCallback onHistory;
  final VoidCallback onCompare;

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    final unit = str(row['unit']);
    final perQuintal = unit.isEmpty || RegExp(r'quintal|qtl|100 ?kg', caseSensitive: false).hasMatch(unit);
    String rupees(Object? v) => v is num ? '₹${v.round()}' : '—';
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: FarmCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Text(str(row['market'], 'fos.market.market'.tr()),
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700, color: ink)),
            ),
            ProvenanceBadge.maybe(row['provenance']) ?? const SizedBox.shrink(),
          ]),
          Text(
              '${[
                row['district'],
                row['state']
              ].where((e) => e != null).map(phrase).join(', ')} · ${str(row['variety']).toLowerCase().startsWith('demo standard') ? 'fos.market.variety_not_stated'.tr() : phrase(str(row['variety'], 'fos.market.variety_not_stated'.tr()))}',
              style: TextStyle(fontSize: 13, color: mutedColor(context))),
          const SizedBox(height: 6),
          Text(
              '${rupees(row['modal_price'])} ${perQuintal ? 'fos.market2.per_quintal'.tr() : phrase(unit.replaceFirst('INR/', ''))}',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: ink)),
          Text(
              'fos.market.low_high'.tr(namedArgs: {
                'low': rupees(row['min_price']),
                'high': rupees(row['max_price']),
                'date': row['arrival_date'] == null
                    ? 'fos.market.date_not_supplied'.tr()
                    : displayDate(str(row['arrival_date']))
              }),
              style: TextStyle(fontSize: 13, color: mutedColor(context))),
          Row(children: [
            TextButton(onPressed: onHistory, child: Text('fos.market.history'.tr())),
            TextButton(onPressed: onCompare, child: Text('fos.market.compare'.tr())),
          ]),
        ]),
      ),
    );
  }
}

/// Client-only arithmetic from the farmer's own quantities and costs.
class _TakeHome extends StatefulWidget {
  const _TakeHome({required this.rows, required this.onClear});

  final List<Map<String, dynamic>> rows;
  final VoidCallback onClear;

  @override
  State<_TakeHome> createState() => _TakeHomeState();
}

class _TakeHomeState extends State<_TakeHome> {
  final _qty = TextEditingController();
  final _costs = <String, (TextEditingController, TextEditingController)>{};

  bool _qualifies(Map<String, dynamic> r) =>
      r['modal_price'] is num && RegExp(r'quintal|qtl|100 ?kg', caseSensitive: false).hasMatch(str(r['unit']));

  @override
  Widget build(BuildContext context) {
    final qty = double.tryParse(_qty.text);
    final nets = <double?>[];
    for (final r in widget.rows) {
      final c = _costs.putIfAbsent(
          str(r['series_id'], str(r['market'])), () => (TextEditingController(), TextEditingController()));
      nets.add(qty == null || !_qualifies(r)
          ? null
          : qty * (r['modal_price'] as num) - (double.tryParse(c.$1.text) ?? 0) - (double.tryParse(c.$2.text) ?? 0));
    }
    final best = nets.whereType<double>().fold<double?>(null, (a, b) => a == null || b > a ? b : a);
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
      child: SingleChildScrollView(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
                child: Text('fos.market2.calc_title'.tr(),
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700, color: inkColor(context)))),
            TextButton(onPressed: widget.onClear, child: Text('fos.market.clear'.tr())),
          ]),
          TextField(
            controller: _qty,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(labelText: 'fos.market.your_quantity'.tr()),
            onChanged: (_) => setState(() {}),
          ),
          for (var i = 0; i < widget.rows.length; i++) ...[
            const SizedBox(height: 8),
            Text(str(widget.rows[i]['market']),
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: inkColor(context))),
            if (!_qualifies(widget.rows[i]))
              Text('fos.market.not_per_quintal'.tr(), style: TextStyle(color: mutedColor(context)))
            else
              Row(children: [
                Expanded(
                  child: TextField(
                    controller: _costs[str(widget.rows[i]['series_id'], str(widget.rows[i]['market']))]!.$1,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(labelText: 'fos.market.transport'.tr()),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _costs[str(widget.rows[i]['series_id'], str(widget.rows[i]['market']))]!.$2,
                    keyboardType: TextInputType.number,
                    decoration: InputDecoration(labelText: 'fos.market.other_charges'.tr()),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
              ]),
            if (nets[i] != null)
              Text(
                  'fos.market.net_line'.tr(namedArgs: {
                    'label': (nets[i] == best ? 'fos.market.highest_return' : 'fos.market.estimated_take_home').tr(),
                    'amount': '₹${nets[i]!.round()}'
                  }),
                  style: TextStyle(
                      fontWeight: FontWeight.w700,
                      color: nets[i] == best
                          ? (context.isDark ? AppColors.primaryLight : AppColors.primaryDark)
                          : inkColor(context))),
          ],
          const SizedBox(height: 6),
          Text('fos.market.own_estimate'.tr(), style: TextStyle(fontSize: 12, color: mutedColor(context))),
        ]),
      ),
    );
  }
}

class _Suggest extends StatefulWidget {
  const _Suggest({required this.controller, required this.label, required this.options});

  final TextEditingController controller;
  final String label;
  final List<String> options;

  @override
  State<_Suggest> createState() => _SuggestState();
}

class _SuggestState extends State<_Suggest> {
  final _focus = FocusNode();

  @override
  void dispose() {
    _focus.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => RawAutocomplete<String>(
        textEditingController: widget.controller,
        focusNode: _focus,
        optionsBuilder: (v) => v.text.isEmpty
            ? const Iterable.empty()
            : widget.options.where((o) => o.toLowerCase().contains(v.text.toLowerCase())).take(8),
        fieldViewBuilder: (context, c, focus, submit) =>
            TextField(controller: c, focusNode: focus, decoration: InputDecoration(labelText: widget.label)),
        optionsViewBuilder: (context, select, items) => Align(
          alignment: Alignment.topLeft,
          child: Material(
            elevation: 4,
            color: Theme.of(context).cardColor,
            borderRadius: BorderRadius.circular(12),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 240, maxWidth: 320),
              child: ListView(shrinkWrap: true, children: [
                for (final o in items) ListTile(title: Text(o), onTap: () => select(o)),
              ]),
            ),
          ),
        ),
      );
}
