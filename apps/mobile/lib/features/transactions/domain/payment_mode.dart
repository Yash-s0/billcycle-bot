enum PaymentMode {
  card,
  upi,
  cash;

  String get value => name;

  static PaymentMode fromValue(String raw) {
    return PaymentMode.values.firstWhere(
      (mode) => mode.value == raw,
      orElse: () => PaymentMode.card,
    );
  }
}
