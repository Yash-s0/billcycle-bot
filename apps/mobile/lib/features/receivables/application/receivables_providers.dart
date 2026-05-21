import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../domain/person_pending_summary.dart';

final receivablesProvider = StreamProvider<List<PersonPendingSummary>>((Ref ref) {
  return ref.watch(receivablesRepositoryProvider).watchPendingByPerson();
});
