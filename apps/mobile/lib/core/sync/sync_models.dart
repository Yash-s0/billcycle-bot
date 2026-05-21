class PendingOperation {
  const PendingOperation({
    required this.id,
    required this.entityType,
    required this.entityId,
    required this.operationType,
    required this.payload,
    required this.createdAt,
    required this.attempts,
    this.lastError,
  });

  final String id;
  final String entityType;
  final String entityId;
  final String operationType;
  final String payload;
  final DateTime createdAt;
  final int attempts;
  final String? lastError;

  factory PendingOperation.fromMap(Map<String, Object?> map) {
    return PendingOperation(
      id: map['id']! as String,
      entityType: map['entity_type']! as String,
      entityId: map['entity_id']! as String,
      operationType: map['operation_type']! as String,
      payload: map['payload']! as String,
      createdAt: DateTime.parse(map['created_at']! as String).toUtc(),
      attempts: map['attempts']! as int,
      lastError: map['last_error'] as String?,
    );
  }
}

class SyncStatus {
  const SyncStatus({
    required this.enabled,
    required this.deviceId,
    this.serverCursor,
    this.lastSyncAt,
    required this.pendingCount,
  });

  final bool enabled;
  final String deviceId;
  final String? serverCursor;
  final DateTime? lastSyncAt;
  final int pendingCount;
}

class SyncRunResult {
  const SyncRunResult({
    required this.success,
    required this.pushedCount,
    required this.pulledCount,
    this.error,
  });

  final bool success;
  final int pushedCount;
  final int pulledCount;
  final String? error;
}

class PushResult {
  const PushResult({
    required this.ackedOperationIds,
    required this.serverCursor,
    required this.conflicts,
  });

  final List<String> ackedOperationIds;
  final String? serverCursor;
  final List<Map<String, Object?>> conflicts;
}

class PullResult {
  const PullResult({
    required this.changes,
    required this.serverCursor,
  });

  final List<Map<String, Object?>> changes;
  final String? serverCursor;
}
