import '../../../core/contracts/repositories.dart';
import '../../../core/db/app_database.dart';
import '../../../core/db/map_utils.dart';
import '../../../core/db/table_names.dart';
import '../../../core/sync/outbox_queue.dart';
import '../domain/payment_mode.dart';
import '../domain/transaction_model.dart';

class TransactionsRepositoryImpl implements TransactionsRepository {
  TransactionsRepositoryImpl(this._database)
      : _outbox = OutboxQueue(_database);

  final AppDatabase _database;
  final OutboxQueue _outbox;

  @override
  Stream<List<TransactionModel>> watchTransactions({
    PaymentMode? paymentMode,
    String? cardId,
  }) {
    return _database.watchTableQuery(TableNames.transactions, () async {
      final StringBuffer sql = StringBuffer('SELECT * FROM transactions WHERE 1=1');
      final List<Object?> params = <Object?>[];

      if (paymentMode != null) {
        sql.write(' AND payment_mode = ?');
        params.add(paymentMode.value);
      }
      if (cardId != null && cardId.isNotEmpty) {
        sql.write(' AND card_id = ?');
        params.add(cardId);
      }
      sql.write(' ORDER BY txn_date DESC, created_at DESC');

      return _database.query(sql.toString(), params: params);
    }).map((List<Map<String, Object?>> rows) {
      return rows.map(_fromRow).toList(growable: false);
    });
  }

  @override
  Future<TransactionModel?> findById(String id) async {
    final List<Map<String, Object?>> rows = await _database.query(
      'SELECT * FROM transactions WHERE id = ? LIMIT 1',
      params: <Object?>[id],
    );
    if (rows.isEmpty) {
      return null;
    }
    return _fromRow(rows.first);
  }

  @override
  Future<List<TransactionModel>> listRecent({
    int limit = 10,
    int offset = 0,
  }) async {
    final List<Map<String, Object?>> rows = await _database.query(
      '''
      SELECT * FROM transactions
      ORDER BY txn_date DESC, created_at DESC
      LIMIT ? OFFSET ?
      ''',
      params: <Object?>[limit, offset],
    );

    return rows.map(_fromRow).toList(growable: false);
  }

  @override
  Future<void> upsert(TransactionModel transaction) async {
    await _database.transaction(() async {
      await _database.executeInsert(
        '''
        INSERT OR REPLACE INTO transactions (
          id, card_id, payment_mode, amount, discount_amount, cashback_amount,
          final_amount, txn_date, is_for_someone_else, person_id,
          reimbursement_status, category, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        params: <Object?>[
          transaction.id,
          transaction.cardId,
          transaction.paymentMode.value,
          transaction.amount,
          transaction.discountAmount,
          transaction.cashbackAmount,
          transaction.finalAmount,
          transaction.txnDate.toUtc().toIso8601String(),
          transaction.isForSomeoneElse ? 1 : 0,
          transaction.personId,
          transaction.reimbursementStatus.value,
          transaction.category,
          transaction.notes,
          transaction.createdAt.toUtc().toIso8601String(),
          transaction.updatedAt.toUtc().toIso8601String(),
        ],
      );

      await _outbox.enqueue(
        entityType: 'transaction',
        entityId: transaction.id,
        operationType: 'upsert',
        payload: transaction.toMap(),
      );

      _database.notifyTables(
        <String>{
          TableNames.transactions,
          TableNames.pendingOperations,
          TableNames.notificationEvents,
          TableNames.cardBillPayments,
        },
      );
    });
  }

  @override
  Future<void> deleteById(String id) async {
    await _database.transaction(() async {
      await _database.executeDelete(
        'DELETE FROM transactions WHERE id = ?',
        params: <Object?>[id],
      );

      await _outbox.enqueue(
        entityType: 'transaction',
        entityId: id,
        operationType: 'delete',
        payload: <String, Object?>{'id': id},
      );

      _database.notifyTables(
        <String>{
          TableNames.transactions,
          TableNames.pendingOperations,
          TableNames.notificationEvents,
          TableNames.cardBillPayments,
        },
      );
    });
  }

  TransactionModel _fromRow(Map<String, Object?> row) {
    final Map<String, Object?> normalized = <String, Object?>{
      ...row,
      'amount': readDouble(row, 'amount'),
      'discount_amount': readDouble(row, 'discount_amount'),
      'cashback_amount': readDouble(row, 'cashback_amount'),
      'final_amount': readDouble(row, 'final_amount'),
      'is_for_someone_else': readInt(row, 'is_for_someone_else'),
    };
    return TransactionModel.fromMap(normalized);
  }
}
