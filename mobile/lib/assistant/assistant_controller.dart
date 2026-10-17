import 'dart:async';
import 'dart:convert';

import 'package:easy_localization/easy_localization.dart';
import 'package:flutter_riverpod/legacy.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../core/api.dart';
import '../core/config.dart';
import '../core/language.dart';
import '../core/offline.dart';
import '../core/session.dart';
import '../core/workspace_cache.dart';
import 'models.dart';
import 'run_events.dart';

class AssistantState {
  const AssistantState({
    this.ready = false,
    this.loading = false,
    this.running = false,
    this.recovering = false,
    this.messages = const [],
    this.pending,
    this.tasks = const [],
    this.deletedTasks = const [],
    this.artifacts = const [],
    this.attachments = const [],
    this.conversations = const [],
    this.catalog = const Catalog(),
    this.error,
    this.status = '',
    this.outbox = const [],
  });

  final bool ready;
  final bool loading;
  final bool running;

  /// Following a run that was in progress when the app last closed.
  final bool recovering;
  final List<ChatMessage> messages;
  final Pending? pending;
  final List<FarmTask> tasks;
  final List<FarmTask> deletedTasks;
  final List<Artifact> artifacts;
  final List<Attachment> attachments;
  final List<Conversation> conversations;
  final Catalog catalog;
  final String? error;
  final String status;

  /// Messages typed with no network; sent in order when it returns.
  final List<String> outbox;

  bool get busy => running || recovering;

  AssistantState copyWith({
    bool? ready,
    bool? loading,
    bool? running,
    bool? recovering,
    List<ChatMessage>? messages,
    Pending? pending,
    bool clearPending = false,
    List<FarmTask>? tasks,
    List<FarmTask>? deletedTasks,
    List<Artifact>? artifacts,
    List<Attachment>? attachments,
    List<Conversation>? conversations,
    Catalog? catalog,
    String? error,
    bool clearError = false,
    String? status,
    List<String>? outbox,
  }) =>
      AssistantState(
        ready: ready ?? this.ready,
        loading: loading ?? this.loading,
        running: running ?? this.running,
        recovering: recovering ?? this.recovering,
        messages: messages ?? this.messages,
        pending: clearPending ? null : pending ?? this.pending,
        tasks: tasks ?? this.tasks,
        deletedTasks: deletedTasks ?? this.deletedTasks,
        artifacts: artifacts ?? this.artifacts,
        attachments: attachments ?? this.attachments,
        conversations: conversations ?? this.conversations,
        catalog: catalog ?? this.catalog,
        error: clearError ? null : error ?? this.error,
        status: status ?? this.status,
        outbox: outbox ?? this.outbox,
      );
}

/// Page context sent with a run so the assistant knows where the farmer is.
class RunContext {
  const RunContext({this.view = 'assistant', this.selectedDate, this.weatherCity, this.missionId});

  /// assistant | station | calendar | crops | markets | schemes | records | weather
  final String view;
  final String? selectedDate;
  final String? weatherCity;
  final String? missionId;

  Map<String, Object?> toJson() => {
        'workspace_view': view,
        if (selectedDate != null) 'selected_date': selectedDate,
        if (weatherCity != null && weatherCity!.isNotEmpty) 'weather_city': weatherCity,
        if (missionId != null) 'mission_id': missionId,
      };
}

class AssistantController extends StateNotifier<AssistantState> {
  AssistantController(this._api, this._language, this._invalidate,
      {http.Client Function()? streamClient, void Function(String?)? onPreferredLanguage, bool Function()? isOnline})
      : _streamClient = streamClient ?? http.Client.new,
        _onPreferredLanguage = onPreferredLanguage,
        _isOnline = isOnline ?? (() => true),
        super(const AssistantState()) {
    if (_api.session != null) {
      _restoreOutbox();
      load();
    }
  }

  final ApiClient _api;
  final String Function() _language;
  final void Function() _invalidate;
  final http.Client Function() _streamClient;
  final void Function(String?)? _onPreferredLanguage;
  final bool Function() _isOnline;
  http.Client? _active;
  bool _stopRequested = false;
  int _localIds = 0;

  String get _sid => _api.session!.id;
  String _localId() => 'local-${DateTime.now().microsecondsSinceEpoch}-${_localIds++}';

  Future<void> load() async {
    if (_api.session == null || state.loading) return;
    state = state.copyWith(loading: true, clearError: true);
    try {
      final catalog = Catalog.fromJson(await _api.get('/api/assistant/catalog'));
      final snapshot = await _sync();
      if (!mounted) return;
      _onPreferredLanguage?.call(snapshot.preferredLanguage);
      if (state.outbox.isNotEmpty && _isOnline()) unawaited(Future(flushOutbox));
      state = state.copyWith(ready: true, loading: false, catalog: catalog);
      final last = snapshot.messages.isEmpty ? null : snapshot.messages.last;
      if (last != null && last.working && last.serverId != null) unawaited(_recover(last));
    } on ApiException catch (e) {
      if (mounted) state = state.copyWith(loading: false, error: e.message);
    }
  }

  Future<SessionSnapshot> _sync({bool replaceMessages = true}) async {
    final snapshot = SessionSnapshot.fromJson(await _api.get('/api/assistant/sessions/$_sid'));
    if (!mounted) return snapshot;
    state = state.copyWith(
      messages: replaceMessages ? snapshot.messages : null,
      pending: snapshot.pending,
      clearPending: snapshot.pending == null,
      tasks: snapshot.tasks,
      deletedTasks: snapshot.deletedTasks,
      artifacts: snapshot.artifacts,
      attachments: snapshot.attachments,
      conversations: snapshot.conversations,
    );
    return snapshot;
  }

  Future<void> refresh() async {
    if (state.busy) return;
    try {
      await _sync();
    } on ApiException catch (e) {
      if (mounted) state = state.copyWith(error: e.message);
    }
  }

  /// After a restart the server may still be finishing (or have just marked
  /// the run stopped). Replay its persisted events instead of guessing.
  Future<void> _recover(ChatMessage message) async {
    state = state.copyWith(recovering: true, status: 'fos.assistant.reconnecting'.tr());
    var after = 0;
    var current = message.copyWith(text: '', activities: const []);
    final deadline = DateTime.now().add(const Duration(seconds: 90));
    try {
      while (mounted && DateTime.now().isBefore(deadline)) {
        final data = await _api.get('/api/assistant/sessions/$_sid/events',
            query: {'run_id': message.serverId, 'after_sequence': after});
        var terminal = false;
        for (final raw in (data is Map ? data['events'] as List? : null) ?? const []) {
          if (raw is! Map) continue;
          final event = raw.map((k, v) => MapEntry('$k', v));
          after = (event['sequence'] as num?)?.toInt() ?? after;
          final folded = foldEvent(current, event);
          current = folded.message;
          terminal = terminal || folded.terminal;
        }
        _replace(message.id, (_) => current);
        if (terminal) break;
        await Future<void>.delayed(const Duration(seconds: 2));
      }
      if (mounted) await _sync();
    } on ApiException catch (e) {
      if (mounted) state = state.copyWith(error: e.message);
    } finally {
      if (mounted) state = state.copyWith(recovering: false, status: '');
    }
  }

  void _replace(String id, ChatMessage Function(ChatMessage) change) {
    if (!mounted) return;
    state = state.copyWith(messages: [for (final m in state.messages) m.id == id ? change(m) : m]);
  }

  /// Sends a farmer turn (or an answer/approval for the pending card).
  /// [display] is what the farmer sees in their bubble; [message] goes to the
  /// assistant in the farmer's original language.
  Future<void> send(
    String message, {
    String? display,
    RunContext context = const RunContext(),
    List<String> attachmentIds = const [],
    Map<String, String>? answers,
    bool? approval,
    String? pendingId,
  }) async {
    if (state.busy || _api.session == null) return;
    if (!state.ready) await load();
    if (!state.ready) return;
    final assistantId = _localId();
    _stopRequested = false;
    state = state.copyWith(
      running: true,
      clearError: true,
      status: 'fos.assistant.connecting'.tr(),
      clearPending: pendingId != null,
      messages: [
        ...state.messages,
        ChatMessage(id: _localId(), role: Role.user, text: display ?? message),
        ChatMessage(id: assistantId, role: Role.assistant, status: 'working'),
      ],
    );
    final client = _streamClient();
    _active = client;
    var terminal = false;
    try {
      final response = await _api.stream('/api/assistant/sessions/$_sid/run', {
        'message': message,
        'station_id': AppConfig.stationId,
        'language': _language(),
        ...context.toJson(),
        if (attachmentIds.isNotEmpty) 'attachment_ids': attachmentIds,
        if (answers != null) 'answers': answers,
        if (approval != null) 'approval': approval,
        if (pendingId != null) 'pending_id': pendingId,
      }, client);
      await for (final event in ndjsonEvents(response.stream).timeout(const Duration(seconds: 190))) {
        if (!mounted) return;
        final current = state.messages.firstWhere((m) => m.id == assistantId);
        final folded = foldEvent(current, event);
        _replace(assistantId, (_) => folded.message);
        if (folded.status != null) state = state.copyWith(status: folded.status);
        if (folded.pending != null) state = state.copyWith(pending: folded.pending);
        if (event['type'] == 'tool_completed') _invalidate();
        if (folded.artifact != null) {
          state = state.copyWith(artifacts: [folded.artifact!, ...state.artifacts]);
        }
        terminal = terminal || folded.terminal;
      }
      if (!terminal) {
        throw ApiException(0, 'fos.assistant.response_stopped'.tr());
      }
      await _sync();
    } catch (e) {
      if (!mounted) return;
      final stopped = _stopRequested;
      _replace(
        assistantId,
        (m) => m.copyWith(
          status: stopped ? 'stopped' : 'error',
          error: stopped
              ? 'fos.assistant.stopped_saved'.tr()
              : e is ApiException
                  ? e.message
                  : e is TimeoutException
                      ? 'fos.assistant.timed_out'.tr()
                      : 'fos.assistant.connection_interrupted'.tr(),
        ),
      );
      // Pick up whatever the server persisted (pending card, saved records).
      try {
        await _sync(replaceMessages: false);
      } catch (_) {}
    } finally {
      client.close();
      if (identical(_active, client)) _active = null;
      if (mounted) state = state.copyWith(running: false, status: '');
    }
  }

  /// Closing the stream makes the server cancel the run; it persists `stopped`.
  void stop() {
    _stopRequested = true;
    _active?.close();
  }

  /// Retry re-sends the farmer's last plain message.
  Future<void> retryLast({RunContext context = const RunContext()}) async {
    final lastUser = state.messages.lastWhere((m) => m.role == Role.user,
        orElse: () => const ChatMessage(id: '', role: Role.user));
    if (lastUser.text.isEmpty) return;
    await send(lastUser.text, context: context);
  }

  Future<void> approve(Pending pending) =>
      send('Approved', approval: true, pendingId: pending.id);

  Future<void> decline(Pending pending) => send(
      pending.kind == PendingKind.approval ? 'Do not save this' : 'Skip these details',
      approval: false,
      pendingId: pending.id);

  Future<void> answer(Pending pending, Map<String, String> values) {
    final summary = pending.fields
        .map((f) => '${f.prompt}: ${f.type == 'photo' ? 'Photo attached' : values[f.id] ?? ''}')
        .join(' · ');
    return send(summary, answers: values, pendingId: pending.id);
  }

  Future<void> newConversation() async {
    if (state.busy) return;
    try {
      await _api.post('/api/assistant/sessions/$_sid/reset');
      _invalidate();
      state = state.copyWith(messages: const [], clearPending: true, clearError: true);
      await _sync();
    } on ApiException catch (e) {
      state = state.copyWith(error: e.message);
    }
  }

  Future<void> restoreConversation(String id) async {
    if (state.busy) return;
    try {
      await _api.post('/api/assistant/sessions/$_sid/restore/$id');
      await _sync();
    } on ApiException catch (e) {
      state = state.copyWith(error: e.message);
    }
  }

  Future<Attachment> uploadBytes(String filename, List<int> bytes) async {
    if (bytes.length > 5 * 1024 * 1024) {
      throw ApiException(413, 'fos.assistant.file_too_big'.tr());
    }
    final data = await _api.post('/api/assistant/sessions/$_sid/attachments-json',
        body: {'filename': filename.length > 120 ? filename.substring(0, 120) : filename, 'content': base64Encode(bytes)},
        timeout: const Duration(seconds: 45));
    final attachment = Attachment.fromJson((data as Map).map((k, v) => MapEntry('$k', v)));
    if (mounted) state = state.copyWith(attachments: [attachment, ...state.attachments]);
    return attachment;
  }

  Future<String> rewrite(ChatMessage message) async {
    final data = await _api.post(
        '/api/assistant/sessions/$_sid/answers/${Uri.encodeComponent(message.serverId ?? message.id)}/rewrite',
        timeout: const Duration(seconds: 50));
    final text = data is Map ? data['text'] : null;
    if (text is! String || text.isEmpty) throw ApiException(503, 'fos.assistant.no_alternative'.tr());
    return text;
  }

  /// Edit / delete / restore a saved task with optimistic-concurrency checks.
  Future<void> changeTask(FarmTask task, {bool delete = false, bool restore = false}) async {
    if (state.busy) throw ApiException(409, 'fos.assistant.finish_current'.tr());
    // Deleting bumps the row version; restore with the server's latest copy.
    if (restore) task = state.deletedTasks.where((t) => t.id == task.id).firstOrNull ?? task;
    final path = '/api/assistant/sessions/$_sid/tasks/${task.id}';
    final ifMatch = task.rowVersion == null ? null : {'If-Match': '${task.rowVersion}'};
    try {
      if (delete) {
        await _api.delete(path, extraHeaders: ifMatch);
      } else if (restore) {
        await _api.post('$path/restore', extraHeaders: ifMatch);
      } else {
        await _api.patch(path, body: task.toPatch());
      }
    } on ApiException catch (e) {
      if (e.conflict) {
        await _sync(replaceMessages: false);
        throw ApiException(409, 'fos.assistant.task_changed'.tr());
      }
      rethrow;
    } finally {
      _invalidate();
    }
    await _sync(replaceMessages: false);
  }

  String get _outboxKey => 'outbox_${_api.session?.id}';

  Future<void> _restoreOutbox() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getStringList(_outboxKey) ?? const [];
    if (mounted && saved.isNotEmpty) state = state.copyWith(outbox: saved);
  }

  Future<void> _persistOutbox() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_outboxKey, state.outbox);
  }

  /// Keeps a message typed without network; nothing is sent yet.
  Future<void> queue(String message) async {
    if (message.trim().isEmpty) return;
    state = state.copyWith(outbox: [...state.outbox, message.trim()]);
    await _persistOutbox();
  }

  Future<void> removeQueued(int index) async {
    state = state.copyWith(outbox: [...state.outbox]..removeAt(index));
    await _persistOutbox();
  }

  /// Sends waiting messages one by one; stops at a question/approval card
  /// so nothing answers it on the farmer's behalf.
  Future<void> flushOutbox() async {
    while (mounted && state.outbox.isNotEmpty && state.ready && !state.busy && state.pending == null) {
      final next = state.outbox.first;
      state = state.copyWith(outbox: state.outbox.sublist(1));
      await _persistOutbox();
      await send(next);
      final last = state.messages.isEmpty ? null : state.messages.last;
      if (last?.status == 'error' && last?.error != null && mounted) {
        // Network dropped again: put it back at the front and wait.
        state = state.copyWith(outbox: [next, ...state.outbox]);
        await _persistOutbox();
        return;
      }
    }
  }

  @override
  void dispose() {
    _active?.close();
    super.dispose();
  }
}

final assistantProvider = StateNotifierProvider<AssistantController, AssistantState>((ref) {
  final api = ref.watch(apiProvider);
  final controller = AssistantController(
    api,
    () => ref.read(languageProvider).code,
    () => ref.read(workspaceCacheProvider).invalidate(),
    onPreferredLanguage: ref.read(languageProvider.notifier).adoptServerPreference,
    isOnline: () => ref.read(offlineProvider).value != true,
  );
  // Signal is back: send what the farmer typed while offline.
  ref.listen(offlineProvider, (_, next) {
    if (next.value == false) controller.flushOutbox();
  });
  return controller;
});
