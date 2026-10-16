import 'package:flutter/material.dart';

import '../utils/constants.dart';
import 'kit.dart';

/// Where a value came from. Labels match the web `ProvenanceBadge` so a
/// forecast is never shown as a measurement, nor a sample as an observation.
String provenanceLabel(String? origin) => switch (origin) {
      'synthetic' => 'Sample',
      'observed' => 'Observed',
      'reanalysis' => 'Reanalysis',
      'modeled' => 'Modelled',
      'forecast' => 'Forecast',
      'scenario' => 'Scenario',
      'user_reported' || 'farmer_entered' => 'Farmer reported',
      'curated' => 'Reviewed source',
      'derived' => 'Calculated',
      _ => 'Source not supplied',
    };

Color _color(String? origin) => switch (origin) {
      'observed' || 'curated' => AppColors.primaryDark,
      'forecast' || 'modeled' || 'reanalysis' => AppColors.info,
      'scenario' || 'synthetic' => AppColors.warning,
      'user_reported' || 'farmer_entered' => const Color(0xFF7C3AED),
      'derived' => const Color(0xFF0E7490),
      _ => AppColors.textMuted,
    };

class ProvenanceBadge extends StatelessWidget {
  const ProvenanceBadge(this.provenance, {super.key});

  /// `{origin, source, observed_at, stale, unit}` or null.
  final Map<String, dynamic>? provenance;

  static ProvenanceBadge? maybe(Object? value) =>
      value is Map ? ProvenanceBadge(value.map((k, v) => MapEntry('$k', v))) : null;

  @override
  Widget build(BuildContext context) {
    final p = provenance ?? const {};
    final origin = p['origin'] as String?;
    final label = provenanceLabel(origin) + (p['stale'] == true ? ' · Older data' : '');
    final tip = [
      if (p['source'] != null) '${p['source']}',
      if (p['observed_at'] != null) 'Dated ${displayDate('${p['observed_at']}')}',
      if (p['unit'] != null) '${p['unit']}',
    ].join(' · ');
    return Semantics(
      label: 'Data origin: $label',
      child: Tag(label, color: _color(origin), tooltip: tip.isEmpty ? null : tip),
    );
  }
}
