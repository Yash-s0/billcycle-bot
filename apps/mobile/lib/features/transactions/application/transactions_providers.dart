import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../domain/payment_mode.dart';
import '../domain/transaction_model.dart';

class TransactionFilter {
  const TransactionFilter({
    this.mode,
    this.cardId,
  });

  final PaymentMode? mode;
  final String? cardId;

  TransactionFilter copyWith({
    PaymentMode? mode,
    String? cardId,
    bool clearCard = false,
  }) {
    return TransactionFilter(
      mode: mode ?? this.mode,
      cardId: clearCard ? null : (cardId ?? this.cardId),
    );
  }
}

final transactionFilterProvider = StateProvider<TransactionFilter>(
  (Ref ref) => const TransactionFilter(),
);

final filteredTransactionsProvider = StreamProvider<List<TransactionModel>>((Ref ref) {
  final TransactionFilter filter = ref.watch(transactionFilterProvider);
  return ref.watch(transactionsRepositoryProvider).watchTransactions(
        paymentMode: filter.mode,
        cardId: filter.cardId,
      );
});

final recentTransactionsProvider = FutureProvider<List<TransactionModel>>((Ref ref) {
  return ref.watch(transactionsRepositoryProvider).listRecent(limit: 10, offset: 0);
});
