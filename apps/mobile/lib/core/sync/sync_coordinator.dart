import 'dart:convert';

import '../db/app_database.dart';
import '../db/table_names.dart';
import '../logging/app_logger.dart';
import 'sync_client.dart';
import 'sync_models.dart';

class SyncCoordinator {
  SyncCoordinator({
    required AppDatabase database,
    required SyncClient client,
  })  : _database = database,
        _client = client;

  final AppDatabase _database;
  final SyncClient _client;

  Future<SyncRunResult> runSync({bool force = false}) async {
    if (!_client.isEnabled) {
      return const SyncRunResult(
        success: false,
        pushedCount: 0,
        pulledCount: 0,
        error: 'Sync disabled: missing SYNC_BASE_URL',
      );
    }

    try {
      final Map<String, Object?> syncState = (await _database.query(
        'SELECT device_id, server_cursor, sync_enabled FROM sync_state WHERE id = 1',
      ))
          .first;
      final String deviceId = syncState['device_id']! as String;
      final String? cursor = syncState['server_cursor'] as String?;
      final bool enabled = (syncState['sync_enabled'] as int? ?? 0) == 1;

      if (!enabled && !force) {
        return const SyncRunResult(
          success: false,
          pushedCount: 0,
          pulledCount: 0,
          error: 'Sync disabled in settings',
        );
      }

      final List<Map<String, Object?>> pendingRows = await _database.query(
        'SELECT * FROM pending_operations ORDER BY created_at ASC LIMIT 200',
      );
      final List<PendingOperation> pendingOps = pendingRows
          .map(PendingOperation.fromMap)
          .toList(growable: false);

      int pushed = 0;
      String? nextCursor = cursor;
      if (pendingOps.isNotEmpty) {
        final PushResult pushResult = await _client.push(
          deviceId: deviceId,
          operations: pendingOps,
          lastKnownCursor: cursor,
        );
        pushed = pushResult.ackedOperationIds.length;
        nextCursor = pushResult.serverCursor ?? nextCursor;

        if (pushResult.ackedOperationIds.isNotEmpty) {
          final String placeholders = List<String>.filled(
            pushResult.ackedOperationIds.length,
            '?',
          ).join(',');
          await _database.executeDelete(
            'DELETE FROM pending_operations WHERE id IN ($placeholders)',
            params: pushResult.ackedOperationIds,
            table: TableNames.pendingOperations,
          );
        }
      }

      final PullResult pullResult = await _client.pull(
        deviceId: deviceId,
        cursor: nextCursor,
      );
      final int pulled = pullResult.changes.length;

      if (pullResult.changes.isNotEmpty) {
        await _database.transaction(() async {
          for (final Map<String, Object?> change in pullResult.changes) {
            await _applyChange(change);
          }
        });
      }

      await _database.executeUpdate(
        '''
        UPDATE sync_state
        SET server_cursor = ?, last_sync_at = ?
        WHERE id = 1
        ''',
        params: <Object?>[
          pullResult.serverCursor ?? nextCursor,
          DateTime.now().toUtc().toIso8601String(),
        ],
        table: TableNames.syncState,
      );

      return SyncRunResult(
        success: true,
        pushedCount: pushed,
        pulledCount: pulled,
      );
    } catch (error, stackTrace) {
      AppLogger.log.warning('Sync failed: $error', error, stackTrace);
      return SyncRunResult(
        success: false,
        pushedCount: 0,
        pulledCount: 0,
        error: error.toString(),
      );
    }
  }

  Future<void> _applyChange(Map<String, Object?> change) async {
    final String entityType = change['entityType']! as String;
    final String operationType = change['operationType']! as String;
    final Map<String, dynamic> payload =
        jsonDecode(change['payload']! as String) as Map<String, dynamic>;

    if (operationType == 'delete') {
      final String id = (change['entityId'] ?? payload['id']) as String;
      switch (entityType) {
        case 'card':
          await _database.executeDelete(
            'DELETE FROM cards WHERE id = ?',
            params: <Object?>[id],
            table: TableNames.cards,
          );
          break;
        case 'transaction':
          await _database.executeDelete(
            'DELETE FROM transactions WHERE id = ?',
            params: <Object?>[id],
            table: TableNames.transactions,
          );
          break;
      }
      return;
    }

    switch (entityType) {
      case 'card':
        await _database.executeInsert(
          '''
          INSERT OR REPLACE INTO cards (
            id, bank_name, card_name, billing_day, due_day,
            credit_limit, notes, created_at, updated_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
          ''',
          params: <Object?>[
            payload['id'],
            payload['bank_name'],
            payload['card_name'],
            payload['billing_day'],
            payload['due_day'],
            payload['credit_limit'],
            payload['notes'],
            payload['created_at'],
            payload['updated_at'],
          ],
          table: TableNames.cards,
        );
        break;
      case 'transaction':
        await _database.executeInsert(
          '''
          INSERT OR REPLACE INTO transactions (
            id, card_id, payment_mode, amount, discount_amount,
            cashback_amount, final_amount, txn_date, is_for_someone_else,
            person_id, reimbursement_status, category, notes, created_at, updated_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
          ''',
          params: <Object?>[
            payload['id'],
            payload['card_id'],
            payload['payment_mode'],
            payload['amount'],
            payload['discount_amount'],
            payload['cashback_amount'],
            payload['final_amount'],
            payload['txn_date'],
            payload['is_for_someone_else'],
            payload['person_id'],
            payload['reimbursement_status'],
            payload['category'],
            payload['notes'],
            payload['created_at'],
            payload['updated_at'],
          ],
          table: TableNames.transactions,
        );
        break;
    }
  }
}
