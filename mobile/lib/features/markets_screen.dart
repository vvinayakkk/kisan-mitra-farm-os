import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../assistant/helper_sheet.dart';
import '../assistant/widgets/farm_result.dart';
import '../core/api.dart';
import '../core/workspace_cache.dart';
import '../ui/kit.dart';
import '../ui/loader.dart';
import '../ui/provenance.dart';
import '../utils/constants.dart';
import 'saathi.dart';
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
  Map<String, dynamic>? _prices;
  Map<String, dynamic>? _trend;
  Map<String, dynamic> _catalogue = const {};
  String? _error;
  bool _busy = false;
  int _shown = 9;
  final _compare = <Map<String, dynamic>>[];

  @override
  void initState() {
    super.initState();
    _loadCatalogue();
    _search();
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
    final args = {'commodity': crop, 'state': _state.text.trim(), if (market != null) 'market': market};
    final results = await Future.wait([
      tools.inspect('market_prices', args).then<Object>((v) => v, onError: (Object e) => e),
      tools.inspect('market_trend', args).then<Object>((v) => v, onError: (Object e) => e),
    ]);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _prices = results[0] is Map ? results[0] as Map<String, dynamic> : null;
      _trend = results[1] is Map ? results[1] as Map<String, dynamic> : null;
      if (_prices == null) {
        _error = results[0] is ApiException ? (results[0] as ApiException).message : 'Prices could not be loaded.';
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    final rows = asMaps(_prices?['rates'] ?? _prices?['records'])
        .where((r) => str(r['arrival_date']).compareTo(_today) <= 0 || str(r['arrival_date']).isEmpty)
        .toList();
    final markets = asMaps(_catalogue['markets']).take(12).toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Market prices')),
      floatingActionButton: const HelperButton(contextKey: 'markets'),
      body: FarmBackground(
        child: ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 96), children: [
          const PreparedBySaathi(area: 'markets'),
          FarmCard(
            child: Column(children: [
              _Suggest(controller: _crop, label: 'Crop', options: (_catalogue['commodities'] as List? ?? const []).map((e) => '$e').toList()),
              const SizedBox(height: 8),
              _Suggest(controller: _state, label: 'State (optional)', options: (_catalogue['states'] as List? ?? const []).map((e) => '$e').toList()),
              const SizedBox(height: 8),
              Row(children: [
                if (_market != null)
                  Expanded(child: InputChip(label: Text(_market!), onDeleted: () => _search())),
                const Spacer(),
                FilledButton.icon(
                  onPressed: _busy
                      ? null
                      : () {
                          HapticFeedback.selectionClick();
                          _search(market: _market);
                        },
                  icon: const Icon(Icons.search),
                  label: const Text('Look up'),
                ),
              ]),
            ]),
          ),
          if (_busy) const LoadingView('Loading…'),
          if (_error != null) ErrorView(_error!, onRetry: () => _search(market: _market)),
          if (!_busy && _prices != null) ...[
            SectionTitle(_crop.text.trim(),
                trailing: ProvenanceBadge.maybe(_prices!['provenance'])),
            Text('${str(_prices!['source'], 'Mandi prices')} · dated records, not offers',
                style: TextStyle(fontSize: 12, color: mutedColor(context))),
            const SizedBox(height: 6),
            if (rows.isEmpty)
              EmptyView(
                title: 'No reported prices.',
                detail: str(_prices!['message']).isEmpty ? null : str(_prices!['message']),
              )
            else ...[
              for (final r in rows.take(_shown)) _PriceCard(row: r, onHistory: () => _search(market: str(r['market'])), onCompare: () {
                    setState(() {
                      if (_compare.length >= 3) _compare.removeAt(0);
                      _compare.add(r);
                    });
                  }),
              if (rows.length > _shown)
                TextButton(onPressed: () => setState(() => _shown += 9), child: const Text('More')),
            ],
            if (_compare.isNotEmpty) _TakeHome(rows: _compare, onClear: () => setState(_compare.clear)),
            const SectionTitle('Trend'),
            if (_trend != null && ChartData.tryParse(_trend!['chart']) != null)
              FarmResult(_trend!)
            else
              Text('Not enough data for a trend.',
                  style: TextStyle(color: mutedColor(context))),
            if (markets.isNotEmpty)
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: Text('Mandi directory · ${markets.length}', style: TextStyle(color: ink)),
                children: [
                  for (final m in markets)
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      title: Text(str(m['name'])),
                      subtitle: Text([m['district'], m['state']].where((e) => e != null).join(', ')),
                      trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                        if (str(m['source_url']).startsWith('https://'))
                          IconButton(
                            tooltip: 'Source',
                            icon: const Icon(Icons.open_in_new, size: 18),
                            onPressed: () => launchUrl(Uri.parse(str(m['source_url'])), mode: LaunchMode.externalApplication),
                          ),
                        TextButton(onPressed: () => _search(market: str(m['name'])), child: const Text('Select')),
                      ]),
                    ),
                ],
              ),
            TextButton.icon(
              onPressed: () => context.push('/exchange'),
              icon: const Icon(Icons.handshake_outlined),
              label: const Text('Farmer exchange'),
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
    final unit = str(row['unit']).replaceFirst('INR/', '');
    String rupees(Object? v) => v is num ? '₹${v.round()}' : '—';
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: FarmCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Expanded(
              child: Text(str(row['market'], 'Market'), style: TextStyle(fontWeight: FontWeight.w700, color: ink)),
            ),
            ProvenanceBadge.maybe(row['provenance']) ?? const SizedBox.shrink(),
          ]),
          Text('${[row['district'], row['state']].where((e) => e != null).join(', ')} · ${str(row['variety'], 'variety not stated')}',
              style: TextStyle(fontSize: 12, color: mutedColor(context))),
          const SizedBox(height: 6),
          Text('${rupees(row['modal_price'])} / ${unit.isEmpty ? 'quintal' : unit}',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: ink)),
          Text('Low ${rupees(row['min_price'])} · High ${rupees(row['max_price'])} · ${str(row['arrival_date'], 'date not supplied')}',
              style: TextStyle(fontSize: 12, color: mutedColor(context))),
          Row(children: [
            TextButton(onPressed: onHistory, child: const Text('History')),
            TextButton(onPressed: onCompare, child: const Text('Compare')),
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
      final c = _costs.putIfAbsent(str(r['series_id'], str(r['market'])), () => (TextEditingController(), TextEditingController()));
      nets.add(qty == null || !_qualifies(r)
          ? null
          : qty * (r['modal_price'] as num) - (double.tryParse(c.$1.text) ?? 0) - (double.tryParse(c.$2.text) ?? 0));
    }
    final best = nets.whereType<double>().fold<double?>(null, (a, b) => a == null || b > a ? b : a);
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: FarmCard(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            const Expanded(child: Text('Take-home estimate', style: TextStyle(fontWeight: FontWeight.w700))),
            TextButton(onPressed: widget.onClear, child: const Text('Clear')),
          ]),
          TextField(
            controller: _qty,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'Your quantity (quintals)'),
            onChanged: (_) => setState(() {}),
          ),
          for (var i = 0; i < widget.rows.length; i++) ...[
            const SizedBox(height: 8),
            Text(str(widget.rows[i]['market']), style: const TextStyle(fontWeight: FontWeight.w600)),
            if (!_qualifies(widget.rows[i]))
              const Text('Unit is not per quintal; not compared.')
            else
              Row(children: [
                Expanded(
                  child: TextField(
                    controller: _costs[str(widget.rows[i]['series_id'], str(widget.rows[i]['market']))]!.$1,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'Transport ₹'),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _costs[str(widget.rows[i]['series_id'], str(widget.rows[i]['market']))]!.$2,
                    keyboardType: TextInputType.number,
                    decoration: const InputDecoration(labelText: 'Other charges ₹'),
                    onChanged: (_) => setState(() {}),
                  ),
                ),
              ]),
            if (nets[i] != null)
              Text('${nets[i] == best ? 'Highest estimated return' : 'Estimated take-home'}: ₹${nets[i]!.round()}',
                  style: TextStyle(fontWeight: FontWeight.w700, color: nets[i] == best ? AppColors.primaryDark : null)),
          ],
          const SizedBox(height: 6),
          Text('Your own estimate, not a quote.',
              style: TextStyle(fontSize: 11.5, color: mutedColor(context))),
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
