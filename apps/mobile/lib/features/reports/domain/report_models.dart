class CardBreakdownItem {
  const CardBreakdownItem({
    required this.label,
    required this.totalBilled,
    required this.totalDiscount,
    required this.totalCashback,
    required this.effectiveNet,
  });

  final String label;
  final double totalBilled;
  final double totalDiscount;
  final double totalCashback;
  final double effectiveNet;
}

class PeriodReport {
  const PeriodReport({
    required this.from,
    required this.to,
    required this.totalSpent,
    required this.totalDiscount,
    required this.totalCashback,
    required this.cardBillToRepay,
    required this.amountOwedByOthers,
    required this.topNotes,
    required this.breakdown,
  });

  final DateTime from;
  final DateTime to;
  final double totalSpent;
  final double totalDiscount;
  final double totalCashback;
  final double cardBillToRepay;
  final double amountOwedByOthers;
  final List<MapEntry<String, double>> topNotes;
  final List<CardBreakdownItem> breakdown;
}

class CardSummary {
  const CardSummary({
    required this.cardId,
    required this.cardLabel,
    required this.cycleStart,
    required this.cycleEnd,
    required this.totalSpend,
    required this.totalDiscount,
    required this.totalCashback,
    required this.pendingReceivables,
    required this.upcomingDueDate,
  });

  final String cardId;
  final String cardLabel;
  final DateTime cycleStart;
  final DateTime cycleEnd;
  final double totalSpend;
  final double totalDiscount;
  final double totalCashback;
  final double pendingReceivables;
  final DateTime upcomingDueDate;
}
