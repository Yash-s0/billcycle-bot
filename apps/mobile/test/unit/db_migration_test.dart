import 'package:billcycle_mobile/core/db/app_database.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('creates expected tables and schema version', () async {
    final AppDatabase db = await AppDatabase.openInMemory();

    final versionRow = await db.query('PRAGMA user_version');
    final int version = (versionRow.first['user_version'] as num).toInt();
    expect(version, 3);

    final tables = await db.query(
      "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
    );
    final names = tables.map((row) => row['name'] as String).toSet();

    expect(names, contains('cards'));
    expect(names, contains('transactions'));
    expect(names, contains('pending_operations'));
    expect(names, contains('notification_events'));
    expect(names, contains('notification_ingestion_events'));

    await db.close();
  });
}
