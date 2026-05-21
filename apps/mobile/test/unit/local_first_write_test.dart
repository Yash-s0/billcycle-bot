import 'package:billcycle_mobile/core/db/app_database.dart';
import 'package:billcycle_mobile/features/cards/data/cards_repository_impl.dart';
import 'package:billcycle_mobile/features/cards/domain/card_model.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('card upsert writes local row and enqueues outbox operation', () async {
    final AppDatabase db = await AppDatabase.openInMemory();
    final CardsRepositoryImpl repo = CardsRepositoryImpl(db);

    final CardModel card = CardModel(
      id: 'card-1',
      bankName: 'Axis',
      cardName: 'Magnus',
      billingDay: 12,
      dueDay: 20,
      creditLimit: 500000,
      notes: 'Primary card',
      createdAt: DateTime.utc(2026, 1, 1),
      updatedAt: DateTime.utc(2026, 1, 1),
    );

    await repo.upsert(card);

    final cards = await db.query('SELECT * FROM cards WHERE id = ?', params: <Object?>['card-1']);
    final outbox = await db.query('SELECT * FROM pending_operations WHERE entity_id = ?', params: <Object?>['card-1']);

    expect(cards.length, 1);
    expect(outbox.length, 1);
    expect(outbox.first['operation_type'], 'upsert');

    await db.close();
  });
}
