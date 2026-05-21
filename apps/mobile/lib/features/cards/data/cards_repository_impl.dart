import '../../../core/contracts/repositories.dart';
import '../../../core/db/app_database.dart';
import '../../../core/db/map_utils.dart';
import '../../../core/db/table_names.dart';
import '../../../core/sync/outbox_queue.dart';
import '../domain/card_model.dart';

class CardsRepositoryImpl implements CardsRepository {
  CardsRepositoryImpl(this._database) : _outbox = OutboxQueue(_database);

  final AppDatabase _database;
  final OutboxQueue _outbox;

  @override
  Stream<List<CardModel>> watchCards() {
    return _database.watchTableQuery(TableNames.cards, () async {
      final List<Map<String, Object?>> rows = await _database.query(
        '''
        SELECT * FROM cards
        ORDER BY bank_name ASC, card_name ASC, created_at DESC
        ''',
      );
      return rows;
    }).map((List<Map<String, Object?>> rows) {
      return rows.map(_fromRow).toList(growable: false);
    });
  }

  @override
  Future<CardModel?> findById(String id) async {
    final List<Map<String, Object?>> rows = await _database.query(
      'SELECT * FROM cards WHERE id = ? LIMIT 1',
      params: <Object?>[id],
    );
    if (rows.isEmpty) {
      return null;
    }
    return _fromRow(rows.first);
  }

  @override
  Future<void> upsert(CardModel card) async {
    await _database.transaction(() async {
      await _database.executeInsert(
        '''
        INSERT OR REPLACE INTO cards (
          id, bank_name, card_name, billing_day, due_day, credit_limit, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        params: <Object?>[
          card.id,
          card.bankName,
          card.cardName,
          card.billingDay,
          card.dueDay,
          card.creditLimit,
          card.notes,
          card.createdAt.toUtc().toIso8601String(),
          card.updatedAt.toUtc().toIso8601String(),
        ],
      );

      await _outbox.enqueue(
        entityType: 'card',
        entityId: card.id,
        operationType: 'upsert',
        payload: card.toMap(),
      );

      _database.notifyTables(<String>{TableNames.cards, TableNames.pendingOperations,
          TableNames.cardBillPayments});
    });
  }

  @override
  Future<void> deleteById(String id) async {
    await _database.transaction(() async {
      await _database.executeDelete(
        'DELETE FROM cards WHERE id = ?',
        params: <Object?>[id],
      );

      await _outbox.enqueue(
        entityType: 'card',
        entityId: id,
        operationType: 'delete',
        payload: <String, Object?>{'id': id},
      );

      _database.notifyTables(
        <String>{
          TableNames.cards,
          TableNames.transactions,
          TableNames.pendingOperations,
          TableNames.cardBillPayments,
        },
      );
    });
  }

  CardModel _fromRow(Map<String, Object?> row) {
    final Map<String, Object?> normalized = <String, Object?>{
      ...row,
      'billing_day': readInt(row, 'billing_day'),
      'due_day': readInt(row, 'due_day'),
      'credit_limit': row['credit_limit'] == null ? null : readDouble(row, 'credit_limit'),
    };
    return CardModel.fromMap(normalized);
  }
}
