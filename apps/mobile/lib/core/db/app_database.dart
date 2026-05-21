import 'dart:async';
import 'dart:io';

import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import 'schema_migrations.dart';

class AppDatabase extends DatabaseConnectionUser {
  AppDatabase._(super.executor) : _attached = _ManualGeneratedDatabase(executor);

  final _ManualGeneratedDatabase _attached;

  @override
  GeneratedDatabase get attachedDatabase => _attached;

  final Map<String, StreamController<void>> _tableControllers =
      <String, StreamController<void>>{};
  final Uuid _uuid = const Uuid();

  static Future<AppDatabase> open() async {
    final Directory dir = await getApplicationDocumentsDirectory();
    final File file = File(p.join(dir.path, 'billcycle.sqlite'));
    final QueryExecutor executor = LazyDatabase(
      () async => NativeDatabase(file, logStatements: false),
    );

    final AppDatabase database = AppDatabase._(executor);
    await database._runMigrations();
    await database._seedDefaults();
    return database;
  }

  static Future<AppDatabase> openInMemory() async {
    final AppDatabase database = AppDatabase._(NativeDatabase.memory());
    await database._runMigrations();
    await database._seedDefaults();
    return database;
  }

  Future<void> _runMigrations() async {
    // Enforce idempotent table/index creation on every startup so partially
    // initialized DB files recover automatically.
    for (final String statement in SchemaMigrations.createStatementsV1()) {
      await customStatement(statement);
    }
    for (final String statement in SchemaMigrations.createStatementsV2()) {
      await customStatement(statement);
    }
    for (final String statement in SchemaMigrations.createStatementsV3()) {
      await customStatement(statement);
    }

    final int version = await _schemaVersion();
    if (version != SchemaMigrations.currentVersion) {
      await _setSchemaVersion(SchemaMigrations.currentVersion);
    }
  }

  Future<void> _seedDefaults() async {
    final String now = DateTime.now().toUtc().toIso8601String();
    await customStatement(
      '''
      INSERT OR IGNORE INTO reminder_settings (id, reminders_enabled, reminder_time, timezone, updated_at)
      VALUES (1, 1, '09:00', 'Asia/Kolkata', ?)
      ''',
      <Object?>[now],
    );

    final String deviceId = _uuid.v4();
    await customStatement(
      '''
      INSERT OR IGNORE INTO sync_state (id, device_id, server_cursor, last_sync_at, sync_enabled)
      VALUES (1, ?, NULL, NULL, 0)
      ''',
      <Object?>[deviceId],
    );
  }

  Future<int> _schemaVersion() async {
    final List<QueryRow> rows = await customSelect('PRAGMA user_version').get();
    if (rows.isEmpty) {
      return 0;
    }
    return rows.first.read<int>('user_version');
  }

  Future<void> _setSchemaVersion(int version) async {
    await customStatement('PRAGMA user_version = $version');
  }

  Future<List<Map<String, Object?>>> query(
    String sql, {
    List<Object?> params = const <Object?>[],
  }) async {
    final String statement = _interpolateSql(sql, params);
    final List<QueryRow> rows = await customSelect(statement).get();
    return rows.map((QueryRow row) => row.data).toList(growable: false);
  }

  Future<int> executeInsert(
    String sql, {
    List<Object?> params = const <Object?>[],
    String? table,
  }) async {
    final int result = await customInsert(_interpolateSql(sql, params));
    if (table != null) {
      notifyTable(table);
    }
    return result;
  }

  Future<int> executeUpdate(
    String sql, {
    List<Object?> params = const <Object?>[],
    String? table,
  }) async {
    final int result = await customUpdate(_interpolateSql(sql, params));
    if (table != null) {
      notifyTable(table);
    }
    return result;
  }

  Future<int> executeDelete(
    String sql, {
    List<Object?> params = const <Object?>[],
    String? table,
  }) async {
    final int result = await customUpdate(_interpolateSql(sql, params));
    if (table != null) {
      notifyTable(table);
    }
    return result;
  }

  Stream<List<Map<String, Object?>>> watchTableQuery(
    String table,
    Future<List<Map<String, Object?>>> Function() loader,
  ) async* {
    yield await loader();
    await for (final _ in _controllerForTable(table).stream) {
      yield await loader();
    }
  }

  void notifyTable(String table) {
    _controllerForTable(table).add(null);
  }

  void notifyTables(Iterable<String> tables) {
    for (final String table in tables) {
      notifyTable(table);
    }
  }

  Stream<void> tableChanges(String table) {
    return _controllerForTable(table).stream;
  }

  StreamController<void> _controllerForTable(String table) {
    return _tableControllers.putIfAbsent(
      table,
      () => StreamController<void>.broadcast(),
    );
  }

  String _interpolateSql(String sql, List<Object?> params) {
    if (params.isEmpty) {
      return sql;
    }

    final StringBuffer out = StringBuffer();
    int paramIndex = 0;

    for (int i = 0; i < sql.length; i += 1) {
      final String ch = sql[i];
      if (ch == '?' && paramIndex < params.length) {
        out.write(_toSqlLiteral(params[paramIndex]));
        paramIndex += 1;
      } else {
        out.write(ch);
      }
    }

    return out.toString();
  }

  String _toSqlLiteral(Object? value) {
    if (value == null) {
      return 'NULL';
    }
    if (value is num) {
      return value.toString();
    }
    if (value is bool) {
      return value ? '1' : '0';
    }

    final String escaped = value.toString().replaceAll("'", "''");
    return "'$escaped'";
  }

  @override
  Future<void> close() async {
    for (final StreamController<void> controller in _tableControllers.values) {
      await controller.close();
    }
    _tableControllers.clear();
    await super.close();
  }
}

class _ManualGeneratedDatabase extends GeneratedDatabase {
  _ManualGeneratedDatabase(super.executor);

  @override
  MigrationStrategy get migration => MigrationStrategy(
        onCreate: (Migrator m) async {},
        onUpgrade: (Migrator m, int from, int to) async {},
      );

  @override
  Iterable<TableInfo<Table, Object?>> get allTables => const <TableInfo<Table, Object?>>[];

  @override
  List<DatabaseSchemaEntity> get allSchemaEntities => const <DatabaseSchemaEntity>[];

  @override
  int get schemaVersion => SchemaMigrations.currentVersion;
}
