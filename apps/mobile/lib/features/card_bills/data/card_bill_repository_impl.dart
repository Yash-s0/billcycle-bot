import 'package:uuid/uuid.dart';

import '../../../core/db/app_database.dart';
import '../../../core/db/map_utils.dart';
import '../../../core/db/table_names.dart';
import '../../../core/utils/billing_cycle.dart';
import '../domain/card_bill_pending_item.dart';

class CardBillRepositoryImpl {
  CardBillRepositoryImpl(this._database);

  final AppDatabase _database;
  final Uuid _uuid = const Uuid();

  Stream<List<CardBillPendingItem>> watchPendingItems({DateTime? today}) {
    final DateTime now = (today ?? DateTime.now()).toUtc();
    return _database.watchTableQuery(TableNames.cardBillPayments, () async {
      final List<Map<String, Object?>> cards = await _database.query('SELECT * FROM cards');
      final List<CardBillPendingItem> items = <CardBillPendingItem>[];

      for (final Map<String, Object?> card in cards) {
        final String cardId = readString(card, 'id');
        final ({DateTime start, DateTime end}) cycle = getCurrentBillingCycle(
          billingDay: readInt(card, 'billing_day'),
          today: now,
        );

        final List<Map<String, Object?>> billedRows = await _database.query(
          '''
          SELECT COALESCE(SUM(final_amount - cashback_amount), 0) AS billed
          FROM transactions
          WHERE card_id = ?
            AND payment_mode = 'card'
            AND date(txn_date) BETWEEN date(?) AND date(?)
          ''',
          params: <Object?>[
            cardId,
            asIsoDate(cycle.start),
            asIsoDate(cycle.end),
          ],
        );

        final List<Map<String, Object?>> paidRows = await _database.query(
          '''
          SELECT COALESCE(SUM(amount_paid), 0) AS paid
          FROM card_bill_payments
          WHERE card_id = ?
            AND date(cycle_start) = date(?)
            AND date(cycle_end) = date(?)
          ''',
          params: <Object?>[
            cardId,
            asIsoDate(cycle.start),
            asIsoDate(cycle.end),
          ],
        );

        final double billed = readDouble(billedRows.first, 'billed');
        final double paid = readDouble(paidRows.first, 'paid');
        final double pending = ((billed - paid).clamp(0, double.infinity) as num).toDouble();

        items.add(
          CardBillPendingItem(
            cardId: cardId,
            cardLabel: '${readString(card, 'bank_name')}/${readString(card, 'card_name')}',
            cycleStart: cycle.start,
            cycleEnd: cycle.end,
            dueDate: getNextDueDate(
              dueDay: readInt(card, 'due_day'),
              today: now,
            ),
            billedAmount: billed,
            paidAmount: paid,
            pendingAmount: pending,
          ),
        );
      }

      items.sort((CardBillPendingItem a, CardBillPendingItem b) => b.pendingAmount.compareTo(a.pendingAmount));
      return items
          .map(
            (CardBillPendingItem item) => <String, Object?>{
              'card_id': item.cardId,
              'card_label': item.cardLabel,
              'cycle_start': item.cycleStart.toIso8601String(),
              'cycle_end': item.cycleEnd.toIso8601String(),
              'due_date': item.dueDate.toIso8601String(),
              'billed': item.billedAmount,
              'paid': item.paidAmount,
              'pending': item.pendingAmount,
            },
          )
          .toList(growable: false);
    }).map(
      (List<Map<String, Object?>> rows) => rows
          .map(
            (Map<String, Object?> row) => CardBillPendingItem(
              cardId: readString(row, 'card_id'),
              cardLabel: readString(row, 'card_label'),
              cycleStart: DateTime.parse(readString(row, 'cycle_start')).toUtc(),
              cycleEnd: DateTime.parse(readString(row, 'cycle_end')).toUtc(),
              dueDate: DateTime.parse(readString(row, 'due_date')).toUtc(),
              billedAmount: readDouble(row, 'billed'),
              paidAmount: readDouble(row, 'paid'),
              pendingAmount: readDouble(row, 'pending'),
            ),
          )
          .toList(growable: false),
    );
  }

  Future<void> markPaid({
    required CardBillPendingItem item,
    required double amountPaid,
    String? notes,
  }) async {
    await _database.executeInsert(
      '''
      INSERT INTO card_bill_payments (
        id, card_id, cycle_start, cycle_end, amount_paid, paid_at, notes
      ) VALUES (?, ?, ?, ?, ?, ?, ?)
      ''',
      params: <Object?>[
        _uuid.v4(),
        item.cardId,
        asIsoDate(item.cycleStart),
        asIsoDate(item.cycleEnd),
        amountPaid,
        DateTime.now().toUtc().toIso8601String(),
        notes,
      ],
      table: TableNames.cardBillPayments,
    );
  }
}
