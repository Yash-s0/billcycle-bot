import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/sync/sync_models.dart';

final syncStatusProvider = FutureProvider<SyncStatus>((Ref ref) {
  return ref.watch(syncRepositoryProvider).getStatus();
});
