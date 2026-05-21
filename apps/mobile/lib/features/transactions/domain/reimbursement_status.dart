enum ReimbursementStatus {
  own,
  pending,
  partial,
  paid;

  String get value => name;

  static ReimbursementStatus fromValue(String raw) {
    return ReimbursementStatus.values.firstWhere(
      (status) => status.value == raw,
      orElse: () => ReimbursementStatus.own,
    );
  }
}
