import 'dart:async';
import 'dart:convert';

import 'models.dart';

/// Splits an NDJSON byte stream into decoded event maps. Malformed lines are
/// surfaced as errors rather than skipped, so a broken stream is never shown
/// as a finished answer.
Stream<Map<String, dynamic>> ndjsonEvents(Stream<List<int>> bytes) => bytes
    .transform(utf8.decoder)
    .transform(const LineSplitter())
    .where((line) => line.trim().isNotEmpty)
    .map((line) {
      final value = jsonDecode(line);
      if (value is! Map) throw const FormatException('Unexpected stream event');
      return value.map((k, v) => MapEntry('$k', v));
    });

/// Result of folding one server event into the assistant message.
class Folded {
  const Folded(this.message, {this.status, this.pending, this.artifact, this.terminal = false});

  final ChatMessage message;

  /// Short live label from the server (`status`/`tool_started`).
  final String? status;
  final Pending? pending;
  final Artifact? artifact;

  /// done / error / cancelled.
  final bool terminal;
}

/// Pure reducer shared by the live stream and replay after restart, so both
/// paths render exactly the persisted events and nothing else.
Folded foldEvent(ChatMessage m, Map<String, dynamic> e) {
  switch (e['type']) {
    case 'run_started':
      return Folded(m.copyWith(serverId: e['run_id'] as String?), status: e['label'] as String?);
    case 'status':
      return Folded(m, status: e['label'] as String?);
    case 'delta':
      return Folded(m.copyWith(text: m.text + (e['text'] as String? ?? '')));
    case 'tool_started':
      final callId = '${e['call_id']}';
      if (m.activities.any((a) => a.callId == callId)) return Folded(m);
      return Folded(
        m.copyWith(activities: [
          ...m.activities,
          Activity(
            callId: callId,
            tool: '${e['tool']}',
            label: '${e['label'] ?? e['tool']}',
            status: ActivityStatus.running,
          ),
        ]),
        status: e['label'] as String?,
      );
    case 'tool_completed' || 'tool_failed':
      final ok = e['type'] == 'tool_completed';
      final result = e['result'] is Map
          ? (e['result'] as Map).map((k, v) => MapEntry('$k', v))
          : <String, dynamic>{};
      return Folded(
        m.copyWith(
          activities: [
            for (final a in m.activities)
              a.callId == '${e['call_id']}'
                  ? a.finish(
                      ok: ok,
                      result: result,
                      elapsedMs: (e['elapsed_ms'] as num?)?.toInt(),
                      error: e['error'] as String?)
                  : a,
          ],
        ),
        artifact: ok ? Artifact.fromJson(result['artifact']) : null,
      );
    case 'question' || 'approval':
      return Folded(m, pending: Pending.fromJson(e['pending']), status: 'Waiting for you');
    case 'error':
      return Folded(m.copyWith(status: 'error', error: '${e['message'] ?? 'The request failed.'}'),
          terminal: true);
    case 'cancelled':
      return Folded(m.copyWith(status: 'stopped'), terminal: true);
    case 'done':
      return Folded(m.copyWith(status: '${e['status'] ?? 'completed'}'), terminal: true);
    default:
      return Folded(m);
  }
}
