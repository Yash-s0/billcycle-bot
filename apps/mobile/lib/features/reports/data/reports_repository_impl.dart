import '../../../core/contracts/repositories.dart';
import '../../../core/db/app_database.dart';
import '../../../core/db/map_utils.dart';
import '../../../core/utils/billing_cycle.dart';
import '../domain/report_models.dart';

class ReportsRepositoryImpl implements ReportsRepository {
  ReportsRepositoryImpl(this._database);

  final AppDatabase _database;

  @override
  Future<PeriodReport> getPeriodReport({
    required DateTime from,
    required DateTime to,
  }) async {
    final String fromIso = asIsoDate(from);
    final String toIso = asIsoDate(to);

    final List<Map<String, Object?>> rows = await _database.query(
      '''
      SELECT *
      FROM transactions
      WHERE date(txn_date) BETWEEN date(?) AND date(?)
      ''',
      params: <Object?>[fromIso, toIso],
    );

    double totalSpent = 0;
    double totalDiscount = 0;
    double totalCashback = 0;
    double cardBillToRepay = 0;
    double owedByOthers = 0;

    final Map<String, double> noteTotals = <String, double>{};
    final Map<String, _BreakdownAgg> breakdown = <String, _BreakdownAgg>{};

    for (final Map<String, Object?> row in rows) {
      final double finalAmount = readDouble(row, 'final_amount');
      final double discountAmount = readDouble(row, 'discount_amount');
      final double cashbackAmount = readDouble(row, 'cashback_amount');
      final String paymentMode = readString(row, 'payment_mode');
      final bool isForSomeoneElse = readInt(row, 'is_for_someone_else') == 1;

      totalSpent += finalAmount;
      totalDiscount += discountAmount;
      totalCashback += cashbackAmount;

      if (paymentMode == 'card') {
        cardBillToRepay += (finalAmount - cashbackAmount);
      }

      if (isForSomeoneElse) {
        owedByOthers += (finalAmount - cashbackAmount);
      }

      final String note = (row['notes'] as String?)?.trim().isNotEmpty == true
          ? row['notes']! as String
          : 'No notes';
      noteTotals[note] = (noteTotals[note] ?? 0) + finalAmount;

      final String label;
      if (paymentMode == 'card') {
        label = await _cardLabel(row['card_id'] as String?);
      } else if (paymentMode == 'upi') {
        label = 'UPI';
      } else {
        label = 'Cash';
      }

      final _BreakdownAgg agg = breakdown.putIfAbsent(label, () => _BreakdownAgg());
      agg.total += finalAmount;
      agg.discount += discountAmount;
      agg.cashback += cashbackAmount;
    }

    final List<MapEntry<String, double>> topNotes = noteTotals.entries.toList(growable: false)
      ..sort((MapEntry<String, double> a, MapEntry<String, double> b) => b.value.compareTo(a.value));

    final List<CardBreakdownItem> breakdownItems = breakdown.entries
        .map(
          (MapEntry<String, _BreakdownAgg> item) => CardBreakdownItem(
            label: item.key,
            totalBilled: item.value.total,
            totalDiscount: item.value.discount,
            totalCashback: item.value.cashback,
            effectiveNet: item.value.total - item.value.cashback,
          ),
        )
        .toList(growable: false)
      ..sort((CardBreakdownItem a, CardBreakdownItem b) => b.totalBilled.compareTo(a.totalBilled));

    return PeriodReport(
      from: DateTime.utc(from.year, from.month, from.day),
      to: DateTime.utc(to.year, to.month, to.day),
      totalSpent: totalSpent,
      totalDiscount: totalDiscount,
      totalCashback: totalCashback,
      cardBillToRepay: cardBillToRepay,
      amountOwedByOthers: owedByOthers,
      topNotes: topNotes.take(5).toList(growable: false),
      breakdown: breakdownItems,
    );
  }

  @override
  Future<CardSummary?> getCardSummary({
    required String cardId,
    required DateTime today,
  }) async {
    final List<Map<String, Object?>> cardRows = await _database.query(
      'SELECT * FROM cards WHERE id = ? LIMIT 1',
      params: <Object?>[cardId],
    );
    if (cardRows.isEmpty) {
      return null;
    }

    final Map<String, Object?> card = cardRows.first;
    final int billingDay = readInt(card, 'billing_day');
    final int dueDay = readInt(card, 'due_day');
    final ({DateTime start, DateTime end}) cycle = getCurrentBillingCycle(
      billingDay: billingDay,
      today: today,
    );

    final List<Map<String, Object?>> txns = await _database.query(
      '''
      SELECT *
      FROM transactions
      WHERE card_id = ?
        AND date(txn_date) BETWEEN date(?) AND date(?)
      ORDER BY date(txn_date) DESC
      ''',
      params: <Object?>[cardId, asIsoDate(cycle.start), asIsoDate(cycle.end)],
    );

    double spend = 0;
    double discount = 0;
    double cashback = 0;
    double receivable = 0;

    for (final Map<String, Object?> txn in txns) {
      final double finalAmount = readDouble(txn, 'final_amount');
      final double cashbackAmount = readDouble(txn, 'cashback_amount');
      spend += finalAmount;
      discount += readDouble(txn, 'discount_amount');
      cashback += cashbackAmount;
      if (readInt(txn, 'is_for_someone_else') == 1) {
        receivable += (finalAmount - cashbackAmount);
      }
    }

    return CardSummary(
      cardId: readString(card, 'id'),
      cardLabel: '${readString(card, 'bank_name')}/${readString(card, 'card_name')}',
      cycleStart: cycle.start,
      cycleEnd: cycle.end,
      totalSpend: spend,
      totalDiscount: discount,
      totalCashback: cashback,
      pendingReceivables: receivable,
      upcomingDueDate: getNextDueDate(dueDay: dueDay, today: today),
    );
  }

  Future<String> _cardLabel(String? cardId) async {
    if (cardId == null || cardId.isEmpty) {
      return 'Card';
    }
    final List<Map<String, Object?>> rows = await _database.query(
      'SELECT card_name FROM cards WHERE id = ? LIMIT 1',
      params: <Object?>[cardId],
    );
    if (rows.isEmpty) {
      return 'Card';
    }
    return readString(rows.first, 'card_name');
  }
}

class _BreakdownAgg {
  double total = 0;
  double discount = 0;
  double cashback = 0;
}
