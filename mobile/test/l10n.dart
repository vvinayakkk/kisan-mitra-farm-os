// ignore_for_file: implementation_imports
import 'dart:convert';
import 'dart:io';
import 'dart:ui';

import 'package:easy_localization/src/localization.dart';
import 'package:easy_localization/src/translations.dart';

/// Loads the shipped English strings so `.tr()` resolves in unit tests.
void loadEnglish() {
  final map = jsonDecode(File('assets/translations/en.json').readAsStringSync()) as Map<String, dynamic>;
  Localization.load(const Locale('en'), translations: Translations(map));
}
