import '../../../core/contracts/repositories.dart';
import '../../../core/db/app_database.dart';
import '../../../core/db/map_utils.dart';
import '../../../core/db/table_names.dart';
import '../domain/person_pending_summary.dart';

class ReceivablesRepositoryImpl implements ReceivablesRepository {
  ReceivablesRepositoryImpl(this._database);

  final AppDatabase _database;

  @override
  Stream<List<PersonPendingSummary>> watchPendingByPerson() {
    return _database.watchTableQuery(TableNames.transactions, () async {
      return _database.query(
        '''
        SELECT
          p.id AS person_id,
          p.name AS person_name,
          SUM(t.final_amount - t.cashback_amount) AS pending_amount,
          SUM(t.cashback_amount) AS cashback_amount,
          COUNT(t.id) AS txn_count
        FROM transactions t
        JOIN people p ON p.id = t.person_id
        WHERE t.is_for_someone_else = 1
        GROUP BY p.id, p.name
        HAVING pending_amount > 0
        ORDER BY pending_amount DESC
        ''',
      );
    }).map((List<Map<String, Object?>> rows) {
      return rows
          .map(
            (Map<String, Object?> row) => PersonPendingSummary(
              personId: readString(row, 'person_id'),
              personName: readString(row, 'person_name'),
              pendingAmount: readDouble(row, 'pending_amount'),
              cashbackAmount: readDouble(row, 'cashback_amount'),
              totalAmount: readDouble(row, 'pending_amount') + readDouble(row, 'cashback_amount'),
              transactionCount: readInt(row, 'txn_count'),
            ),
          )
          .toList(growable: false);
    });
  }
}
