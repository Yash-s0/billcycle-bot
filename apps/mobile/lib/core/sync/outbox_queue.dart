import 'dart:convert';

import 'package:uuid/uuid.dart';

import '../db/app_database.dart';
import '../db/table_names.dart';

class OutboxQueue {
  OutboxQueue(this._database);

  final AppDatabase _database;
  final Uuid _uuid = const Uuid();

  Future<void> enqueue({
    required String entityType,
    required String entityId,
    required String operationType,
    required Map<String, Object?> payload,
  }) async {
    final String id = _uuid.v4();
    final String now = DateTime.now().toUtc().toIso8601String();
    await _database.executeInsert(
      '''
      INSERT INTO pending_operations (
        id, entity_type, entity_id, operation_type, payload, created_at, attempts, last_error
      ) VALUES (?, ?, ?, ?, ?, ?, 0, NULL)
      ''',
      params: <Object?>[
        id,
        entityType,
        entityId,
        operationType,
        jsonEncode(payload),
        now,
      ],
      table: TableNames.pendingOperations,
    );
  }
}
