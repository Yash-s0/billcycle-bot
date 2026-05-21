class PersonPendingSummary {
  const PersonPendingSummary({
    required this.personId,
    required this.personName,
    required this.pendingAmount,
    required this.cashbackAmount,
    required this.totalAmount,
    required this.transactionCount,
  });

  final String personId;
  final String personName;
  final double pendingAmount;
  final double cashbackAmount;
  final double totalAmount;
  final int transactionCount;
}
