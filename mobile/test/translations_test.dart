import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

Map<String, String> _flat(Map<String, dynamic> m, [String prefix = '']) => {
      for (final e in m.entries)
        ...(e.value is Map<String, dynamic>
            ? _flat(e.value as Map<String, dynamic>, '$prefix${e.key}.')
            : {'$prefix${e.key}': '${e.value}'}),
    };

Map<String, String> _load(String lang) =>
    _flat(jsonDecode(File('assets/translations/$lang.json').readAsStringSync()) as Map<String, dynamic>);

void main() {
  test('every key used in code exists in English and Hindi with the same placeholders', () {
    final en = _load('en'), hi = _load('hi');
    final used = <String>{};
    for (final f in Directory('lib').listSync(recursive: true).whereType<File>().where((f) => f.path.endsWith('.dart'))) {
      used.addAll(RegExp(r"'(fos\.[a-z_]+\.[a-z0-9_]+)'").allMatches(f.readAsStringSync()).map((m) => m.group(1)!));
    }
    final placeholders = RegExp(r'\{\w+\}');
    for (final key in used) {
      expect(en.containsKey(key), isTrue, reason: 'missing English: $key');
      expect(hi.containsKey(key), isTrue, reason: 'missing Hindi: $key');
      expect(placeholders.allMatches(hi[key]!).map((m) => m[0]).toSet(),
          placeholders.allMatches(en[key]!).map((m) => m[0]).toSet(),
          reason: 'placeholder mismatch: $key');
    }
  });
}
