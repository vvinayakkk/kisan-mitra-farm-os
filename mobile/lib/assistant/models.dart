/// Typed views of the canonical `/api/assistant` contract.
library;

import 'dart:convert';

import 'package:easy_localization/easy_localization.dart';

Map<String, dynamic> _map(Object? v) =>
    v is Map ? v.map((k, v) => MapEntry('$k', v)) : <String, dynamic>{};
List<Map<String, dynamic>> _maps(Object? v) =>
    v is List ? v.whereType<Map>().map(_map).toList() : const [];
String _s(Object? v, [String fallback = '']) => v is String ? v : (v == null ? fallback : '$v');
int? _i(Object? v) => v is int ? v : (v is num ? v.toInt() : int.tryParse('${v ?? ''}'));

enum ActivityStatus { running, done, error }

/// One persisted tool call. Only the server creates these; the app never
/// invents progress rows.
class Activity {
  const Activity({
    required this.callId,
    required this.tool,
    required this.label,
    required this.status,
    this.result = const {},
    this.elapsedMs,
    this.error,
  });

  final String callId;
  final String tool;
  final String label;
  final ActivityStatus status;
  final Map<String, dynamic> result;
  final int? elapsedMs;
  final String? error;

  factory Activity.fromJson(Map<String, dynamic> j) => Activity(
        callId: _s(j['call_id']),
        tool: _s(j['tool']),
        label: _s(j['label'], _s(j['tool'])),
        status: switch (j['status']) {
          'done' => ActivityStatus.done,
          'error' => ActivityStatus.error,
          _ => ActivityStatus.running,
        },
        result: _map(j['result']),
        elapsedMs: _i(j['elapsed_ms']),
        error: j['error'] as String?,
      );

  Activity finish({required bool ok, Map<String, dynamic>? result, int? elapsedMs, String? error}) =>
      Activity(
        callId: callId,
        tool: tool,
        label: label,
        status: ok ? ActivityStatus.done : ActivityStatus.error,
        result: result ?? const {},
        elapsedMs: elapsedMs,
        error: error,
      );

  /// Outcome wording mirrors what the result actually says.
  String get outcome {
    if (status == ActivityStatus.running) return 'fos.assistant.in_progress'.tr();
    if (status == ActivityStatus.error) return error ?? 'fos.assistant.failed'.tr();
    if (tool == 'load_skill') return 'fos.assistant.workflow_loaded'.tr();
    if (result['artifact'] != null) return 'fos.assistant.file_created'.tr();
    if (result['available'] == false) return 'fos.assistant.data_unavailable'.tr();
    if (result['saved'] == true) return 'fos.assistant.saved_workspace'.tr();
    return 'fos.assistant.finished'.tr();
  }
}

enum Role { user, assistant }

class ChatMessage {
  const ChatMessage({
    required this.id,
    required this.role,
    this.text = '',
    this.activities = const [],
    this.status,
    this.error,
    this.serverId,
  });

  final String id;
  final Role role;
  final String text;
  final List<Activity> activities;

  /// Server status: working | completed | waiting | stopped | error.
  final String? status;
  final String? error;

  /// Run id, needed for answer rewrite and event replay.
  final String? serverId;

  bool get working => status == 'working';

  factory ChatMessage.fromJson(Map<String, dynamic> j, String fallbackId) => ChatMessage(
        id: _s(j['id'], fallbackId),
        role: j['role'] == 'user' ? Role.user : Role.assistant,
        text: readableHistory(_s(j['content'])),
        activities: _maps(j['activities']).map(Activity.fromJson).toList(),
        status: j['status'] as String?,
        error: j['error'] as String?,
        serverId: _s(j['id'], fallbackId),
      );

  ChatMessage copyWith({
    String? text,
    List<Activity>? activities,
    String? status,
    String? error,
    String? serverId,
  }) =>
      ChatMessage(
        id: id,
        role: role,
        text: text ?? this.text,
        activities: activities ?? this.activities,
        status: status ?? this.status,
        error: error ?? this.error,
        serverId: serverId ?? this.serverId,
      );
}

/// Hides server-side framing that is stored with user turns.
String readableHistory(String text) {
  text = text.replaceFirst(
      RegExp(r'^Calendar context: selected date \d{4}-\d{2}-\d{2}\. Farmer request: '), '');
  const prefix = 'Requested details: ';
  if (!text.startsWith(prefix)) return text;
  try {
    final answers = _map(_map(jsonDecode(text.substring(prefix.length)))['farmer_answers']);
    if (answers.isEmpty) return text;
    return answers.entries.map((e) => '${e.key.replaceAll('_', ' ')}: ${e.value}').join(' · ');
  } catch (_) {
    return text;
  }
}

class QuestionField {
  const QuestionField({required this.id, required this.label, required this.type, this.options = const []});

  final String id;
  final String label;

  /// text | number | select | date | photo
  final String type;
  final List<String> options;

  String get prompt => label.replaceAll(RegExp(r'\s*\(e\.g\.,[^)]*\)', caseSensitive: false), '');

  factory QuestionField.fromJson(Map<String, dynamic> j) => QuestionField(
        id: _s(j['id']),
        label: _s(j['label']),
        type: _s(j['type'], 'text'),
        options: (j['options'] as List? ?? const []).map((e) => '$e').toList(),
      );
}

enum PendingKind { question, approval }

/// A paused run: either one focused question or one write to review.
class Pending {
  const Pending({
    required this.id,
    required this.kind,
    required this.tool,
    required this.arguments,
    this.reviewLabels = const {},
  });

  final String id;
  final PendingKind kind;
  final String tool;
  final Map<String, dynamic> arguments;
  final Map<String, String> reviewLabels;

  String? get question => arguments['question'] as String?;
  List<QuestionField> get fields => _maps(arguments['fields']).map(QuestionField.fromJson).toList();

  static Pending? fromJson(Object? value) {
    final j = _map(value);
    if (j['id'] is! String) return null;
    return Pending(
      id: j['id'] as String,
      kind: j['kind'] == 'approval' ? PendingKind.approval : PendingKind.question,
      tool: _s(j['tool']),
      arguments: _map(j['arguments']),
      reviewLabels: _map(j['review_labels']).map((k, v) => MapEntry(k, '$v')),
    );
  }
}

class ArtifactPreview {
  const ArtifactPreview({
    required this.title,
    required this.sections,
    required this.columns,
    required this.rows,
    required this.rowCount,
    required this.partial,
  });

  final String title;
  final List<({String heading, String text})> sections;
  final List<String> columns;
  final List<List<Object?>> rows;
  final int rowCount;
  final bool partial;

  static ArtifactPreview? fromJson(Object? value) {
    final j = _map(value);
    if (j.isEmpty) return null;
    return ArtifactPreview(
      title: _s(j['title']),
      sections: _maps(j['sections'])
          .map((s) => (heading: _s(s['heading']), text: _s(s['text'])))
          .toList(),
      columns: (j['columns'] as List? ?? const []).map((e) => '$e').toList(),
      rows: (j['rows'] as List? ?? const []).whereType<List>().map((r) => r.toList()).toList(),
      rowCount: _i(j['row_count']) ?? 0,
      partial: j['partial'] == true,
    );
  }
}

class Artifact {
  const Artifact({
    required this.id,
    required this.fileId,
    required this.title,
    required this.format,
    required this.filename,
    required this.size,
    this.revision,
    this.preview,
  });

  final String id;
  final String fileId;
  final String title;
  final String format;
  final String filename;
  final int size;
  final int? revision;
  final ArtifactPreview? preview;

  static Artifact? fromJson(Object? value) {
    final j = _map(value);
    if (j['file_id'] is! String) return null;
    final format = _s(j['format']);
    return Artifact(
      id: _s(j['id'], j['file_id'] as String),
      fileId: j['file_id'] as String,
      title: _s(j['title'], 'File'),
      format: format,
      filename: _s(j['filename'], '${_s(j['title'], 'file')}.$format'),
      size: _i(j['size']) ?? 0,
      revision: _i(j['revision']),
      preview: ArtifactPreview.fromJson(j['preview']),
    );
  }
}

class FarmTask {
  const FarmTask({
    required this.id,
    required this.title,
    required this.dueDate,
    this.notes = '',
    this.completed = false,
    this.rowVersion,
  });

  final String id;
  final String title;

  /// ISO date (yyyy-mm-dd), farmer-local.
  final String dueDate;
  final String notes;
  final bool completed;
  final int? rowVersion;

  factory FarmTask.fromJson(Map<String, dynamic> j) => FarmTask(
        id: _s(j['id']),
        title: _s(j['title']),
        dueDate: _s(j['due_date']),
        notes: _s(j['notes']),
        completed: j['completed'] == true,
        rowVersion: _i(j['row_version']),
      );

  FarmTask copyWith({String? title, String? dueDate, String? notes, bool? completed}) => FarmTask(
        id: id,
        title: title ?? this.title,
        dueDate: dueDate ?? this.dueDate,
        notes: notes ?? this.notes,
        completed: completed ?? this.completed,
        rowVersion: rowVersion,
      );

  Map<String, dynamic> toPatch() => {
        'title': title,
        'due_date': dueDate,
        'notes': notes,
        'completed': completed,
        if (rowVersion != null) 'row_version': rowVersion,
      };
}

class Attachment {
  const Attachment({required this.id, required this.name, required this.format});

  final String id;
  final String name;
  final String format;

  bool get isPhoto => const {'jpg', 'jpeg', 'png', 'webp'}.contains(format.toLowerCase());

  factory Attachment.fromJson(Map<String, dynamic> j) =>
      Attachment(id: _s(j['id']), name: _s(j['name'], 'File'), format: _s(j['format']));
}

class Conversation {
  const Conversation({required this.id, required this.title, required this.createdAt});

  final String id;
  final String title;
  final String createdAt;

  factory Conversation.fromJson(Map<String, dynamic> j) => Conversation(
      id: _s(j['id']), title: _s(j['title'], 'Conversation'), createdAt: _s(j['created_at']));
}

class CatalogEntry {
  const CatalogEntry({
    required this.id,
    required this.name,
    required this.description,
    this.approval = false,
  });

  final String id;
  final String name;
  final String description;

  /// Tool pauses for farmer review before it changes a record.
  final bool approval;

  factory CatalogEntry.fromJson(Map<String, dynamic> j) => CatalogEntry(
        id: _s(j['id']),
        name: _s(j['name']),
        description: _s(j['description']),
        approval: j['approval'] == true,
      );
}

class Catalog {
  const Catalog({this.skills = const [], this.tools = const []});

  final List<CatalogEntry> skills;
  final List<CatalogEntry> tools;

  factory Catalog.fromJson(Object? value) {
    final j = _map(value);
    return Catalog(
      skills: _maps(j['skills']).map(CatalogEntry.fromJson).toList(),
      tools: _maps(j['tools']).map(CatalogEntry.fromJson).toList(),
    );
  }
}

/// Snapshot returned by `GET /api/assistant/sessions/{sid}`.
class SessionSnapshot {
  const SessionSnapshot({
    required this.messages,
    this.pending,
    this.tasks = const [],
    this.deletedTasks = const [],
    this.artifacts = const [],
    this.attachments = const [],
    this.conversations = const [],
    this.preferredLanguage,
  });

  final List<ChatMessage> messages;
  final Pending? pending;
  final List<FarmTask> tasks;
  final List<FarmTask> deletedTasks;
  final List<Artifact> artifacts;
  final List<Attachment> attachments;
  final List<Conversation> conversations;
  final String? preferredLanguage;

  factory SessionSnapshot.fromJson(Object? value) {
    final j = _map(value);
    final messages = _maps(j['messages']);
    return SessionSnapshot(
      messages: [
        for (var i = 0; i < messages.length; i++) ChatMessage.fromJson(messages[i], 'history-$i'),
      ],
      pending: Pending.fromJson(j['pending']),
      tasks: _maps(j['tasks']).map(FarmTask.fromJson).toList(),
      deletedTasks: _maps(j['deleted_tasks']).map(FarmTask.fromJson).toList(),
      artifacts: _maps(j['artifacts']).map(Artifact.fromJson).whereType<Artifact>().toList(),
      attachments: _maps(j['attachments']).map(Attachment.fromJson).toList(),
      conversations: _maps(j['conversations']).map(Conversation.fromJson).toList(),
      preferredLanguage: j['preferred_language'] as String?,
    );
  }
}
