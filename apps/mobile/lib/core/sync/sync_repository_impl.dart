import '../contracts/repositories.dart';
import '../db/app_database.dart';
import '../db/map_utils.dart';
import '../db/table_names.dart';
import 'sync_client.dart';
import 'sync_coordinator.dart';
import 'sync_models.dart';

class SyncRepositoryImpl implements SyncRepository {
  SyncRepositoryImpl({
    required AppDatabase database,
    required SyncClient client,
  })  : _database = database,
        _coordinator = SyncCoordinator(database: database, client: client),
        _client = client;

  final AppDatabase _database;
  final SyncCoordinator _coordinator;
  final SyncClient _client;

  @override
  Stream<List<PendingOperation>> watchPendingOperations() {
    return _database.watchTableQuery(TableNames.pendingOperations, () async {
      return _database.query(
        'SELECT * FROM pending_operations ORDER BY created_at ASC',
      );
    }).map((List<Map<String, Object?>> rows) {
      return rows.map(PendingOperation.fromMap).toList(growable: false);
    });
  }

  @override
  Future<SyncStatus> getStatus() async {
    final List<Map<String, Object?>> syncRows = await _database.query(
      'SELECT * FROM sync_state WHERE id = 1',
    );
    final List<Map<String, Object?>> pendingRows = await _database.query(
      'SELECT COUNT(*) AS count FROM pending_operations',
    );

    if (syncRows.isEmpty) {
      return const SyncStatus(
        enabled: false,
        deviceId: 'unknown',
        pendingCount: 0,
      );
    }

    final Map<String, Object?> row = syncRows.first;
    return SyncStatus(
      enabled: _client.isEnabled && readInt(row, 'sync_enabled') == 1,
      deviceId: readString(row, 'device_id'),
      serverCursor: row['server_cursor'] as String?,
      lastSyncAt: row['last_sync_at'] == null
          ? null
          : DateTime.parse(readString(row, 'last_sync_at')).toUtc(),
      pendingCount: readInt(pendingRows.first, 'count'),
    );
  }
  @override
  Future<void> setSyncEnabled(bool enabled) async {
    await _database.executeUpdate(
      'UPDATE sync_state SET sync_enabled = ? WHERE id = 1',
      params: <Object?>[enabled ? 1 : 0],
      table: TableNames.syncState,
    );
  }

  @override
  Future<SyncRunResult> runSync({bool force = false}) {
    return _coordinator.runSync(force: force);
  }
}
