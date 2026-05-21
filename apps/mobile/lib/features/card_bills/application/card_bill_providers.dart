import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../domain/card_bill_pending_item.dart';

final cardBillPendingProvider = StreamProvider<List<CardBillPendingItem>>((Ref ref) {
  return ref.watch(cardBillRepositoryProvider).watchPendingItems();
});
