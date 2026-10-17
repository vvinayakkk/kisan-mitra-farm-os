import 'dart:io';

import 'package:easy_localization/easy_localization.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/api.dart';
import '../../core/session.dart';
import '../../ui/kit.dart';
import '../../ui/provenance.dart';
import '../../utils/constants.dart';
import '../models.dart';
import 'theme_helpers.dart';

/// Renders a finished tool result inline: research sources, a generated file,
/// or a dated chart. Anything else renders nothing (the answer text explains).
class FarmResult extends StatelessWidget {
  const FarmResult(this.result, {super.key, this.onRevise});

  final Map<String, dynamic> result;
  final void Function(Artifact)? onRevise;

  static bool isResearch(Map<String, dynamic> r) =>
      r.containsKey('search_suggestions_html') ||
      (r.containsKey('sources') && r.containsKey('retrieved_at'));

  @override
  Widget build(BuildContext context) {
    if (isResearch(result)) return ResearchSources(result);
    final artifact = Artifact.fromJson(result['artifact']);
    if (artifact != null) return FileResult(artifact, onRevise: onRevise);
    final chart = ChartData.tryParse(result['chart']);
    if (chart == null) return const SizedBox.shrink();
    return DatedChart(
      chart,
      provenance: result['provenance'] is Map ? Map<String, dynamic>.from(result['provenance'] as Map) : null,
      source: result['source'] as String?,
    );
  }
}

class ChartData {
  const ChartData({
    required this.title,
    required this.unit,
    required this.points,
    this.kind,
    this.bar = false,
    this.caption,
    this.valueName,
  });

  final String title;
  final String unit;
  final List<({String date, double value})> points;

  /// market | weather_forecast | weather_history | budget
  final String? kind;
  final bool bar;
  final String? caption;
  final String? valueName;

  static ChartData? tryParse(Object? value) {
    if (value is! Map) return null;
    final points = <({String date, double value})>[];
    for (final p in (value['points'] as List? ?? const [])) {
      if (p is Map && p['value'] is num) {
        points.add((date: '${p['date'] ?? ''}', value: (p['value'] as num).toDouble()));
      }
    }
    final bar = value['type'] == 'bar';
    if (points.length < (bar ? 1 : 2)) return null;
    return ChartData(
      title: '${value['title'] ?? 'fos.assistant.chart'.tr()}',
      unit: '${value['unit'] ?? ''}',
      points: points,
      kind: value['kind'] as String?,
      bar: bar,
      caption: value['caption'] as String?,
      valueName: value['value_name'] as String?,
    );
  }
}

class DatedChart extends StatefulWidget {
  const DatedChart(this.chart, {super.key, this.provenance, this.source});

  final ChartData chart;
  final Map<String, dynamic>? provenance;
  final String? source;

  @override
  State<DatedChart> createState() => _DatedChartState();
}

class _DatedChartState extends State<DatedChart> {
  bool _open = true;

  /// Same wording as the web so forecasts, history, scenarios and observed
  /// prices are never confused.
  (String caption, String note, String valueName) _labels() {
    final c = widget.chart;
    final origin = widget.provenance?['origin'];
    final weather = c.kind == 'weather_forecast' || c.kind == 'weather_history';
    final caption = c.caption ??
        (weather
            ? c.kind == 'weather_forecast'
                ? 'fos.assistant.cap_forecast'.tr()
                : 'fos.assistant.cap_history'.tr()
            : c.bar
                ? 'fos.assistant.cap_calculated'.tr()
                : switch (origin) {
                    'synthetic' => 'fos.assistant.cap_synthetic'.tr(),
                    'scenario' => 'fos.assistant.cap_scenario'.tr(),
                    'forecast' => 'fos.assistant.cap_price_forecast'.tr(),
                    _ => 'fos.assistant.cap_dated'.tr(),
                  });
    final note = weather
        ? c.kind == 'weather_forecast'
            ? 'fos.assistant.note_forecast'.tr()
            : 'fos.assistant.note_history'.tr()
        : c.bar
            ? 'fos.assistant.note_costs'.tr()
            : origin == 'synthetic' || origin == 'scenario'
                ? 'fos.assistant.note_fictional'.tr()
                : 'fos.assistant.note_prices'.tr();
    final valueName = c.valueName ??
        (weather
            ? 'fos.assistant.v_rainfall'.tr()
            : c.bar
                ? 'fos.assistant.v_cost'.tr()
                : 'fos.assistant.v_modal'.tr());
    return (caption, note, valueName);
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.chart;
    final (caption, note, valueName) = _labels();
    final ink = inkColor(context);
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: FarmCard(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            InkWell(
              onTap: () => setState(() => _open = !_open),
              child: Row(
                children: [
                  const Icon(Icons.show_chart, size: 18, color: AppColors.primary),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(c.title, style: TextStyle(fontWeight: FontWeight.w700, color: ink)),
                  ),
                  if (widget.provenance != null) ProvenanceBadge(widget.provenance),
                  Icon(_open ? Icons.expand_less : Icons.expand_more, color: ink),
                ],
              ),
            ),
            Text('${c.unit} · $caption', style: TextStyle(fontSize: 12, color: mutedColor(context))),
            if (_open) ...[
              const SizedBox(height: 10),
              Semantics(
                label: 'fos.assistant.chart_semantics'.tr(namedArgs: {
                  'name': valueName,
                  'from': c.points.first.date,
                  'to': c.points.last.date,
                  'count': '${c.points.length}',
                }),
                child: SizedBox(height: 190, child: c.bar ? _bar(context) : _line(context)),
              ),
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(_short(c.points.first.date), style: _axis(context)),
                    Text(_short(c.points.last.date), style: _axis(context)),
                  ],
                ),
              ),
              const SizedBox(height: 6),
              Text([if (widget.source?.isNotEmpty == true) widget.source!, note].join(' · '),
                  style: TextStyle(fontSize: 11.5, color: mutedColor(context))),
            ],
          ],
        ),
      ),
    );
  }

  TextStyle _axis(BuildContext context) => TextStyle(fontSize: 10, color: mutedColor(context));

  String _short(String date) => date.length > 16 ? date.substring(0, 16).replaceFirst('T', ' ') : date;

  LineTouchTooltipData _tooltip(String valueName) => LineTouchTooltipData(
        getTooltipItems: (spots) => spots
            .map((s) => LineTooltipItem(
                '${_short(widget.chart.points[s.x.toInt()].date)}\n$valueName ${s.y.toStringAsFixed(2)}',
                const TextStyle(color: Colors.white, fontSize: 11)))
            .toList(),
      );

  SideTitles _leftTitles(BuildContext context) => SideTitles(
        showTitles: true,
        reservedSize: 44,
        getTitlesWidget: (value, meta) =>
            SideTitleWidget(meta: meta, child: Text(meta.formattedValue, style: _axis(context))),
      );

  Widget _line(BuildContext context) {
    final points = widget.chart.points;
    final (_, _, valueName) = _labels();
    return LineChart(LineChartData(
      gridData: FlGridData(
        drawVerticalLine: false,
        getDrawingHorizontalLine: (_) => FlLine(color: hairlineColor(context), strokeWidth: 1),
      ),
      borderData: FlBorderData(show: false),
      titlesData: FlTitlesData(
        topTitles: const AxisTitles(),
        rightTitles: const AxisTitles(),
        bottomTitles: const AxisTitles(),
        leftTitles: AxisTitles(sideTitles: _leftTitles(context)),
      ),
      lineTouchData: LineTouchData(touchTooltipData: _tooltip(valueName)),
      lineBarsData: [
        LineChartBarData(
          spots: [for (var i = 0; i < points.length; i++) FlSpot(i.toDouble(), points[i].value)],
          color: context.isDark ? AppColors.primaryLight : const Color(0xFF51763A),
          barWidth: 2.5,
          dotData: FlDotData(show: points.length <= 30),
        ),
      ],
    ));
  }

  Widget _bar(BuildContext context) {
    final points = widget.chart.points;
    return BarChart(BarChartData(
      gridData: FlGridData(
        drawVerticalLine: false,
        getDrawingHorizontalLine: (_) => FlLine(color: hairlineColor(context), strokeWidth: 1),
      ),
      borderData: FlBorderData(show: false),
      titlesData: FlTitlesData(
        topTitles: const AxisTitles(),
        rightTitles: const AxisTitles(),
        leftTitles: AxisTitles(sideTitles: _leftTitles(context)),
        bottomTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: points.length <= 8,
            getTitlesWidget: (v, _) => Text(
              points[v.toInt()].date.length > 8 ? points[v.toInt()].date.substring(0, 8) : points[v.toInt()].date,
              style: TextStyle(fontSize: 9, color: mutedColor(context)),
            ),
          ),
        ),
      ),
      barGroups: [
        for (var i = 0; i < points.length; i++)
          BarChartGroupData(x: i, barRods: [
            BarChartRodData(
                toY: points[i].value, color: context.isDark ? AppColors.primaryLight : const Color(0xFF6C8E50), width: 14),
          ]),
      ],
    ));
  }
}

/// Generated document: preview inline, download into app-private storage,
/// open with the phone's viewer, or share.
class FileResult extends ConsumerStatefulWidget {
  const FileResult(this.artifact, {super.key, this.onRevise});

  final Artifact artifact;
  final void Function(Artifact)? onRevise;

  @override
  ConsumerState<FileResult> createState() => _FileResultState();
}

class _FileResultState extends ConsumerState<FileResult> {
  bool _busy = false;
  bool _preview = false;
  String? _error;

  Future<File> _download() async {
    final api = ref.read(apiProvider);
    final session = api.session;
    if (session == null) throw ApiException(401, 'fos.assistant.sign_in_download'.tr());
    final response = await api.bytes('/api/assistant/sessions/${session.id}/files/${widget.artifact.fileId}');
    final dir = Directory('${(await getApplicationDocumentsDirectory()).path}/files/${session.id}');
    await dir.create(recursive: true);
    final safe = widget.artifact.filename.replaceAll(RegExp(r'[^\w.\- ]'), '_');
    final file = File('${dir.path}/$safe');
    await file.writeAsBytes(response.bodyBytes, flush: true);
    return file;
  }

  Future<void> _run(Future<void> Function(File) then) async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await then(await _download());
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } catch (_) {
      setState(() => _error = 'fos.assistant.download_failed'.tr());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = widget.artifact;
    final ink = inkColor(context);
    final kb = (a.size / 1024).toStringAsFixed(a.size < 10240 ? 1 : 0);
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: FarmCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(_icon(a.format), color: accentColor(context)),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(a.title, style: TextStyle(fontWeight: FontWeight.w700, color: ink)),
                      Text(
                        '${a.format.toUpperCase()} · $kb KB · ${'fos.assistant.saved_file'.tr()}'
                        '${(a.revision ?? 1) > 1 ? ' · ${'fos.assistant.version'.tr(namedArgs: {'n': '${a.revision}'})}' : ''}',
                        style: TextStyle(fontSize: 12, color: mutedColor(context)),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                if (a.preview != null)
                  OutlineChip(
                    label: _preview ? 'fos.assistant.hide_preview'.tr() : 'fos.assistant.preview'.tr(),
                    icon: Icons.visibility_outlined,
                    onTap: () => setState(() => _preview = !_preview),
                  ),
                OutlineChip(
                  label: _busy ? 'fos.assistant.downloading'.tr() : 'fos.assistant.open'.tr(),
                  icon: Icons.open_in_new,
                  onTap: _busy
                      ? null
                      : () => _run((f) async {
                            final result = await OpenFilex.open(f.path);
                            if (result.type != ResultType.done && mounted) {
                              setState(() => _error = 'fos.assistant.no_app_opens'.tr(namedArgs: {'format': a.format.toUpperCase()}));
                            }
                          }),
                ),
                OutlineChip(
                  label: 'fos.assistant.share'.tr(),
                  icon: Icons.ios_share,
                  onTap: _busy ? null : () => _run((f) => SharePlus.instance.share(ShareParams(files: [XFile(f.path)], subject: a.title))),
                ),
                if (widget.onRevise != null)
                  OutlineChip(label: 'fos.assistant.revise'.tr(), icon: Icons.edit_outlined, onTap: () => widget.onRevise!(a)),
              ],
            ),
            if (_preview && a.preview != null) _PreviewPaper(a.preview!),
            if (_error != null) ErrorView(_error!),
          ],
        ),
      ),
    );
  }

  IconData _icon(String format) => switch (format) {
        'xlsx' || 'csv' => Icons.table_chart_outlined,
        'pptx' => Icons.slideshow_outlined,
        'pdf' => Icons.picture_as_pdf_outlined,
        _ => Icons.description_outlined,
      };
}

class _PreviewPaper extends StatelessWidget {
  const _PreviewPaper(this.preview);

  final ArtifactPreview preview;

  @override
  Widget build(BuildContext context) {
    final ink = inkColor(context);
    return Container(
      margin: const EdgeInsets.only(top: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: context.isDark ? Colors.black26 : const Color(0xFFFAFAF5),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: hairlineColor(context)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(preview.title, style: TextStyle(fontWeight: FontWeight.w700, color: ink)),
          for (final s in preview.sections) ...[
            const SizedBox(height: 8),
            if (s.heading.isNotEmpty) Text(s.heading, style: TextStyle(fontWeight: FontWeight.w600, color: ink)),
            Text(s.text, style: TextStyle(fontSize: 13, color: ink)),
          ],
          if (preview.columns.isNotEmpty)
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: DataTable(
                headingRowHeight: 34,
                dataRowMinHeight: 30,
                dataRowMaxHeight: 44,
                columns: [for (final c in preview.columns) DataColumn(label: Text(c))],
                rows: [
                  for (final row in preview.rows)
                    DataRow(cells: [
                      for (var i = 0; i < preview.columns.length; i++)
                        DataCell(Text(i < row.length ? '${row[i] ?? '—'}' : '—')),
                    ]),
                ],
              ),
            ),
          if (preview.rowCount > preview.rows.length)
            Text('fos.assistant.showing_rows'.tr(namedArgs: {'shown': '${preview.rows.length}', 'total': '${preview.rowCount}'}),
                style: TextStyle(fontSize: 11, color: mutedColor(context))),
          const SizedBox(height: 6),
          Text(
            (preview.partial
                    ? 'fos.assistant.excerpt_preview'
                    : 'fos.assistant.content_preview').tr(),
            style: TextStyle(fontSize: 11, color: mutedColor(context)),
          ),
        ],
      ),
    );
  }
}

/// Web research evidence. Google Search suggestion chips are shown as links
/// (the provider requires them to be displayed alongside grounded answers).
class ResearchSources extends StatelessWidget {
  const ResearchSources(this.result, {super.key});

  final Map<String, dynamic> result;

  static final _anchor = RegExp(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', dotAll: true);

  @override
  Widget build(BuildContext context) {
    if (result['available'] != true) {
      return Padding(
        padding: const EdgeInsets.only(top: 8),
        child: Text('fos.assistant.research_unavailable'.tr(),
            style: TextStyle(fontSize: 12.5, color: mutedColor(context))),
      );
    }
    final sources = (result['sources'] as List? ?? const [])
        .whereType<Map>()
        .where((s) => '${s['url']}'.startsWith(RegExp(r'https?://')))
        .toList();
    final suggestions = _anchor
        .allMatches('${result['search_suggestions_html'] ?? ''}')
        .map((m) => (url: m.group(1)!, text: m.group(2)!.replaceAll(RegExp(r'<[^>]+>'), '').trim()))
        .where((s) => s.text.isNotEmpty)
        .toList();
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: FarmCard(
        padding: EdgeInsets.zero,
        child: ExpansionTile(
          shape: const Border(),
          leading: Icon(Icons.travel_explore, color: accentColor(context)),
          title: Text('fos.assistant.research_sources'.tr(namedArgs: {'count': '${sources.length}'}),
              style: TextStyle(fontWeight: FontWeight.w600, color: inkColor(context))),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final s in sources)
              ListTile(
                dense: true,
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.link, size: 18),
                title: Text('${s['title'] ?? s['url']}'),
                subtitle: Text(Uri.tryParse('${s['url']}')?.host ?? ''),
                onTap: () => launchUrl(Uri.parse('${s['url']}'), mode: LaunchMode.externalApplication),
              ),
            if (result['retrieved_at'] != null)
              Text('fos.assistant.checked'.tr(namedArgs: {'date': displayDate('${result['retrieved_at']}', withTime: true)}),
                  style: TextStyle(fontSize: 11, color: mutedColor(context))),
            if (suggestions.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('fos.assistant.google_suggestions'.tr(), style: TextStyle(fontSize: 11, color: mutedColor(context))),
              const SizedBox(height: 4),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final s in suggestions)
                  OutlineChip(
                    label: s.text,
                    icon: Icons.search,
                    onTap: () => launchUrl(Uri.parse(s.url), mode: LaunchMode.externalApplication),
                  ),
              ]),
            ],
          ],
        ),
      ),
    );
  }
}
