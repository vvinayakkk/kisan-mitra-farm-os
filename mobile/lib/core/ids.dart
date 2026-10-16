import 'dart:math';

final _random = Random.secure();

/// RFC 4122 v4 UUID for idempotency keys.
String uuidV4() {
  final b = List<int>.generate(16, (_) => _random.nextInt(256));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  final h = b.map((x) => x.toRadixString(16).padLeft(2, '0')).join();
  return '${h.substring(0, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}-${h.substring(16, 20)}-${h.substring(20)}';
}

/// Reuses one key per logical operation until it succeeds, so a retry after a
/// dropped response is recognised by the server instead of duplicated.
class IdempotencyKeys {
  final _keys = <String, String>{};

  String forOperation(String signature) => _keys.putIfAbsent(signature, uuidV4);

  void succeeded(String signature) => _keys.remove(signature);
}
