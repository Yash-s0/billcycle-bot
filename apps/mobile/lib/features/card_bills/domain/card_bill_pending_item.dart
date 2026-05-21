class CardBillPendingItem {
  const CardBillPendingItem({
    required this.cardId,
    required this.cardLabel,
    required this.cycleStart,
    required this.cycleEnd,
    required this.dueDate,
    required this.billedAmount,
    required this.paidAmount,
    required this.pendingAmount,
  });

  final String cardId;
  final String cardLabel;
  final DateTime cycleStart;
  final DateTime cycleEnd;
  final DateTime dueDate;
  final double billedAmount;
  final double paidAmount;
  final double pendingAmount;
}
