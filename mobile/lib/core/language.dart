import 'package:flutter_riverpod/legacy.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Farmer languages the canonical backend accepts (`skyview/languages.py`).
/// The assistant always answers in the language the farmer wrote or spoke in;
/// this preference is only the fallback (and the speech language).
const kAppLanguages = <(String, String)>[
  ('en', 'English'),
  ('hi', 'हिन्दी'),
  ('te', 'తెలుగు'),
  ('ta', 'தமிழ்'),
  ('mr', 'मराठी'),
  ('gu', 'ગુજરાતી'),
  ('bn', 'বাংলা'),
  ('kn', 'ಕನ್ನಡ'),
  ('ml', 'മലയാളം'),
  ('pa', 'ਪੰਜਾਬੀ'),
  ('or', 'ଓଡ଼ିଆ'),
  ('as', 'অসমীয়া'),
  ('ur', 'اردو'),
];

/// Interface translations shipped in assets/translations.
const kUiLocales = {'en', 'hi', 'mr', 'te', 'ta', 'gu', 'bn', 'kn', 'ml', 'pa'};

String? normalizeLanguage(String? value) {
  final prefix = value?.toLowerCase().replaceAll('_', '-').split('-').first;
  final code = prefix == 'od' ? 'or' : prefix;
  return kAppLanguages.any((l) => l.$1 == code) ? code : null;
}

/// BCP-47 code used by the speech routes (`hi-IN`, `od-IN`, ...).
String speechLanguage(String code) => '${code == 'or' ? 'od' : code}-IN';

class LanguagePreference {
  const LanguagePreference(this.code, {this.explicit = false});

  final String code;

  /// The farmer picked it on this device (server preference must not override).
  final bool explicit;
}

class LanguageController extends StateNotifier<LanguagePreference> {
  LanguageController() : super(const LanguagePreference('en')) {
    _load();
  }

  static const _key = 'app_language';

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = normalizeLanguage(prefs.getString(_key));
    if (stored != null && mounted) state = LanguagePreference(stored, explicit: true);
  }

  Future<void> choose(String code) async {
    final value = normalizeLanguage(code);
    if (value == null) return;
    state = LanguagePreference(value, explicit: true);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, value);
  }

  /// Server profile preference applies only until the farmer picks one here.
  void adoptServerPreference(String? code) {
    final value = normalizeLanguage(code);
    if (value != null && !state.explicit) state = LanguagePreference(value);
  }
}

final languageProvider =
    StateNotifierProvider<LanguageController, LanguagePreference>((_) => LanguageController());
