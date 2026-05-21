import '../../features/transactions/domain/payment_mode.dart';

class Validators {
  static String? requiredText(String? value, {String field = 'Field'}) {
    if (value == null || value.trim().isEmpty) {
      return '$field is required';
    }
    return null;
  }

  static String? cardDay(String? value, {String field = 'Day'}) {
    if (requiredText(value, field: field) case final String error?) {
      return error;
    }
    final int? day = int.tryParse(value!.trim());
    if (day == null || day < 1 || day > 31) {
      return '$field must be between 1 and 31';
    }
    return null;
  }

  static String? positiveAmount(String? value, {String field = 'Amount'}) {
    if (requiredText(value, field: field) case final String error?) {
      return error;
    }
    final double? amount = double.tryParse(value!.replaceAll(',', '').trim());
    if (amount == null || amount <= 0) {
      return '$field must be a positive number';
    }
    return null;
  }

  static String? nonNegativeAmount(String? value, {String field = 'Amount'}) {
    if (value == null || value.trim().isEmpty) {
      return null;
    }
    final double? amount = double.tryParse(value.replaceAll(',', '').trim());
    if (amount == null || amount < 0) {
      return '$field must be non-negative';
    }
    return null;
  }

  static String? transactionRules({
    required double amount,
    required double discount,
    required double cashback,
    required PaymentMode paymentMode,
    String? cardId,
    bool isForSomeoneElse = false,
    String? personName,
  }) {
    if (paymentMode == PaymentMode.card && (cardId == null || cardId.isEmpty)) {
      return 'Card is required for card transactions';
    }
    if (discount > amount) {
      return 'Discount cannot exceed amount';
    }
    final double finalAmount = amount - discount;
    if (cashback > finalAmount) {
      return 'Cashback cannot exceed total after discount';
    }
    if (isForSomeoneElse && (personName == null || personName.trim().isEmpty)) {
      return 'Person name is required for reimbursement transactions';
    }
    return null;
  }

  static bool isValidTime(String value) {
    final RegExp regex = RegExp(r'^([01]\\d|2[0-3]):([0-5]\\d)$');
    return regex.hasMatch(value.trim());
  }
}
