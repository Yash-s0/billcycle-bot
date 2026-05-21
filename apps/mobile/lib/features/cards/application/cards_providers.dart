import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../domain/card_model.dart';

final cardsStreamProvider = StreamProvider<List<CardModel>>((Ref ref) {
  return ref.watch(cardsRepositoryProvider).watchCards();
});
