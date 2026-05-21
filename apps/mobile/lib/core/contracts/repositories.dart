import '../../features/cards/domain/card_model.dart';
import '../../features/notifications/domain/notification_event.dart';
import '../../features/receivables/domain/person_pending_summary.dart';
import '../../features/reminders/domain/reminder_settings.dart';
import '../../features/reports/domain/report_models.dart';
import '../../features/transactions/domain/payment_mode.dart';
import '../../features/transactions/domain/transaction_model.dart';
import '../sync/sync_models.dart';

abstract class CardsRepository {
  Stream<List<CardModel>> watchCards();
  Future<CardModel?> findById(String id);
  Future<void> upsert(CardModel card);
  Future<void> deleteById(String id);
}

abstract class TransactionsRepository {
  Stream<List<TransactionModel>> watchTransactions({
    PaymentMode? paymentMode,
    String? cardId,
  });

  Future<List<TransactionModel>> listRecent({
    int limit = 10,
    int offset = 0,
  });

  Future<void> upsert(TransactionModel transaction);
  Future<void> deleteById(String id);
}

abstract class ReportsRepository {
  Future<PeriodReport> getPeriodReport({
    required DateTime from,
    required DateTime to,
  });

  Future<CardSummary?> getCardSummary({
    required String cardId,
    required DateTime today,
  });
}

abstract class ReceivablesRepository {
  Stream<List<PersonPendingSummary>> watchPendingByPerson();
}

abstract class RemindersRepository {
  Future<ReminderSettings> getSettings();
  Future<void> updateSettings(ReminderSettings settings);
  Future<void> generateDailyReminderEvents({DateTime? now});
  Stream<List<NotificationEvent>> watchNotificationEvents();
  Future<void> markNotificationRead(String id);
}

abstract class SyncRepository {
  Stream<List<PendingOperation>> watchPendingOperations();
  Future<SyncStatus> getStatus();
  Future<void> setSyncEnabled(bool enabled);
  Future<SyncRunResult> runSync({bool force = false});
}
