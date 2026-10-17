import 'package:easy_localization/easy_localization.dart';

/// Turns server codes and English catalogue values into farmer words.
/// Unknown values fall back to readable text, never a raw snake_case code.

const _statuses = {
  'open', 'monitoring', 'expert_review', 'needs_expert_review', 'resolved', 'synthetic_example',
  'draft', 'active', 'paused', 'completed', 'cancelled', 'planned', 'growing', 'harvested', 'failed',
  'requested', 'quote_recorded', 'farmer_confirmed', 'farmer_completed', 'published', 'withdrawn',
  'negotiating', 'agreed', 'handover', 'disputed', 'ready', 'approved', 'dismissed',
};

/// `needs_expert_review` → "Needs expert check" (translated).
String statusLabel(Object? code) {
  final c = '${code ?? ''}'.trim();
  if (c.isEmpty) return '';
  return _statuses.contains(c) ? 'fos.label.status_$c'.tr() : humanize(c);
}

const _kinds = {'calendar', 'crop_case', 'mission', 'ledger', 'field_observation', 'soil_report', 'crop_cycle', 'task'};

/// Timeline/record kinds (`crop_case` → "Crop check").
String kindLabel(Object? code) {
  final c = '${code ?? ''}';
  return _kinds.contains(c) ? 'fos.label.kind_$c'.tr() : humanize(c);
}

/// Last-resort readable form of a code: `soil_report` → "Soil report".
String humanize(String code) {
  final t = code.replaceAll(RegExp(r'[_\-.]+'), ' ').trim();
  return t.isEmpty ? t : t[0].toUpperCase() + t.substring(1);
}

const _crops = {
  'wheat', 'rice', 'paddy', 'maize', 'groundnut', 'cotton', 'soybean', 'sugarcane', 'onion', 'potato',
  'tomato', 'chilli', 'turmeric', 'mustard', 'gram', 'tur', 'arhar', 'moong', 'urad', 'bajra', 'jowar',
  'ragi', 'barley', 'banana', 'mango', 'garlic', 'ginger', 'brinjal', 'cabbage', 'cauliflower', 'okra',
  'coriander', 'cumin', 'sunflower', 'sesame', 'coconut', 'apple', 'grapes', 'lentil', 'pea', 'jute',
};

/// Crop names from the catalogue in the farmer's language ("Wheat" → "गेहूं").
String cropName(Object? name) {
  final raw = '${name ?? ''}'.trim();
  final key = raw.toLowerCase().replaceAll(RegExp(r'[^a-z]'), '');
  return _crops.contains(key) ? 'fos.label.crop_$key'.tr() : raw;
}

const _phrases = {
  'standard variety': 'variety_standard',
  'mandi prices': 'source_mandi',
  'reported mandi prices': 'source_mandi_reported',
  'mandi price history': 'source_mandi_history',
  'simulated station readings': 'source_station_simulated',
  'station measurements': 'source_station',
  'regional sharing area': 'area_regional',
};

/// Common fixed catalogue phrases the server sends in English.
String phrase(Object? value) {
  final raw = '${value ?? ''}'.trim();
  final key = _phrases[raw.toLowerCase()];
  return key == null ? raw : 'fos.label.$key'.tr();
}

/// `1.0` → `1`, `2.50` → `2.5`.
String qty(Object? v) {
  if (v is! num) return '${v ?? ''}';
  return v == v.roundToDouble() ? v.toInt().toString() : v.toString();
}

const _flags = {'uncalibrated', 'stale', 'estimated', 'out_of_range', 'missing'};

/// Sensor quality flags (`uncalibrated` → "Not calibrated").
String flagLabel(Object? code) {
  final c = '${code ?? ''}';
  return _flags.contains(c) ? 'fos.label.flag_$c'.tr() : humanize(c);
}
