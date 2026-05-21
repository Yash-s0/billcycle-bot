import 'package:billcycle_mobile/core/validation/validators.dart';
import 'package:billcycle_mobile/features/transactions/domain/payment_mode.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Validators.transactionRules', () {
    test('rejects discount over amount', () {
      final String? error = Validators.transactionRules(
        amount: 100,
        discount: 120,
        cashback: 0,
        paymentMode: PaymentMode.upi,
      );
      expect(error, isNotNull);
    });

    test('rejects cashback over final', () {
      final String? error = Validators.transactionRules(
        amount: 100,
        discount: 20,
        cashback: 90,
        paymentMode: PaymentMode.cash,
      );
      expect(error, isNotNull);
    });

    test('accepts valid card transaction', () {
      final String? error = Validators.transactionRules(
        amount: 100,
        discount: 10,
        cashback: 5,
        paymentMode: PaymentMode.card,
        cardId: 'card-1',
      );
      expect(error, isNull);
    });
  });
}
