class NotificationEvent {
  const NotificationEvent({
    required this.id,
    required this.type,
    required this.title,
    required this.body,
    required this.payload,
    required this.createdAt,
    this.readAt,
  });

  final String id;
  final String type;
  final String title;
  final String body;
  final String payload;
  final DateTime createdAt;
  final DateTime? readAt;

  bool get isRead => readAt != null;

  Map<String, Object?> toMap() {
    return {
      'id': id,
      'type': type,
      'title': title,
      'body': body,
      'payload': payload,
      'created_at': createdAt.toUtc().toIso8601String(),
      'read_at': readAt?.toUtc().toIso8601String(),
    };
  }

  factory NotificationEvent.fromMap(Map<String, Object?> map) {
    return NotificationEvent(
      id: map['id']! as String,
      type: map['type']! as String,
      title: map['title']! as String,
      body: map['body']! as String,
      payload: map['payload']! as String,
      createdAt: DateTime.parse(map['created_at']! as String).toUtc(),
      readAt: map['read_at'] == null ? null : DateTime.parse(map['read_at']! as String).toUtc(),
    );
  }
}
