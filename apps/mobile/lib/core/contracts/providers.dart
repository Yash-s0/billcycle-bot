import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/card_bills/data/card_bill_repository_impl.dart';
import '../../features/cards/data/cards_repository_impl.dart';
import '../../features/receivables/data/receivables_repository_impl.dart';
import '../../features/reminders/data/reminders_repository_impl.dart';
import '../../features/reports/data/reports_repository_impl.dart';
import '../../features/transactions/data/transactions_repository_impl.dart';
import '../db/app_database.dart';
import '../sync/sync_client.dart';
import '../sync/sync_repository_impl.dart';
import 'repositories.dart';

final appDatabaseProvider = Provider<AppDatabase>(
  (Ref ref) => throw UnimplementedError('Database must be overridden at startup'),
);

final syncBaseUrlProvider = Provider<String>(
  (Ref ref) => const String.fromEnvironment('SYNC_BASE_URL', defaultValue: ''),
);

final cardsRepositoryProvider = Provider<CardsRepository>(
  (Ref ref) => CardsRepositoryImpl(ref.watch(appDatabaseProvider)),
);

final transactionsRepositoryProvider = Provider<TransactionsRepository>(
  (Ref ref) => TransactionsRepositoryImpl(ref.watch(appDatabaseProvider)),
);

final reportsRepositoryProvider = Provider<ReportsRepository>(
  (Ref ref) => ReportsRepositoryImpl(ref.watch(appDatabaseProvider)),
);

final receivablesRepositoryProvider = Provider<ReceivablesRepository>(
  (Ref ref) => ReceivablesRepositoryImpl(ref.watch(appDatabaseProvider)),
);

final remindersRepositoryProvider = Provider<RemindersRepository>(
  (Ref ref) => RemindersRepositoryImpl(ref.watch(appDatabaseProvider)),
);

final cardBillRepositoryProvider = Provider<CardBillRepositoryImpl>(
  (Ref ref) => CardBillRepositoryImpl(ref.watch(appDatabaseProvider)),
);

final syncClientProvider = Provider<SyncClient>(
  (Ref ref) => SyncClient(baseUrl: ref.watch(syncBaseUrlProvider)),
);

final syncRepositoryProvider = Provider<SyncRepository>(
  (Ref ref) => SyncRepositoryImpl(
    database: ref.watch(appDatabaseProvider),
    client: ref.watch(syncClientProvider),
  ),
);
