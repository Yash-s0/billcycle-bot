import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app.dart';
import 'core/contracts/providers.dart';
import 'core/db/app_database.dart';
import 'core/logging/app_logger.dart';
import 'core/notifications/transaction_notification_ingestor.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  AppLogger.configure(verbose: false);

  final AppDatabase database = await AppDatabase.open();
  final TransactionNotificationIngestor notificationIngestor =
      TransactionNotificationIngestor(database);
  notificationIngestor.start();

  runApp(
    ProviderScope(
      overrides: <Override>[
        appDatabaseProvider.overrideWithValue(database),
      ],
      child: const BillCycleApp(),
    ),
  );
}
