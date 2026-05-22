import 'dart:async';

import 'package:billcycle_mobile/core/contracts/repositories.dart';
import 'package:billcycle_mobile/core/sync/sync_models.dart';
import 'package:billcycle_mobile/features/notifications/domain/notification_event.dart';
import 'package:billcycle_mobile/features/receivables/domain/person_pending_summary.dart';
import 'package:billcycle_mobile/features/reminders/domain/reminder_settings.dart';
import 'package:billcycle_mobile/features/reports/domain/report_models.dart';
import 'package:billcycle_mobile/features/transactions/domain/payment_mode.dart';
import 'package:billcycle_mobile/features/transactions/domain/transaction_model.dart';

class FakeTransactionsRepository implements TransactionsRepository {
  FakeTransactionsRepository(this._items);

  final List<TransactionModel> _items;

  @override
  Stream<List<TransactionModel>> watchTransactions({PaymentMode? paymentMode, String? cardId}) {
    Iterable<TransactionModel> result = _items;
    if (paymentMode != null) {
      result = result.where((TransactionModel t) => t.paymentMode == paymentMode);
    }
    if (cardId != null) {
      result = result.where((TransactionModel t) => t.cardId == cardId);
    }
    return Stream<List<TransactionModel>>.value(result.toList(growable: false));
  }

  @override
  Future<List<TransactionModel>> listRecent({int limit = 10, int offset = 0}) async => _items;

  @override
  Future<TransactionModel?> findById(String id) async {
    for (final TransactionModel txn in _items) {
      if (txn.id == id) {
        return txn;
      }
    }
    return null;
  }

  @override
  Future<void> upsert(TransactionModel transaction) async {}

  @override
  Future<void> deleteById(String id) async {}
}

class FakeRemindersRepository implements RemindersRepository {
  FakeRemindersRepository(this._events);

  final List<NotificationEvent> _events;

  @override
  Future<void> generateDailyReminderEvents({DateTime? now}) async {}

  @override
  Future<ReminderSettings> getSettings() async =>
      const ReminderSettings(enabled: true, reminderTime: '09:00', timezone: 'Asia/Kolkata');

  @override
  Future<void> markNotificationRead(String id) async {}

  @override
  Future<void> updateSettings(ReminderSettings settings) async {}

  @override
  Stream<List<NotificationEvent>> watchNotificationEvents() =>
      Stream<List<NotificationEvent>>.value(_events);
}

class FakeReceivablesRepository implements ReceivablesRepository {
  FakeReceivablesRepository(this._items);

  final List<PersonPendingSummary> _items;

  @override
  Stream<List<PersonPendingSummary>> watchPendingByPerson() =>
      Stream<List<PersonPendingSummary>>.value(_items);
}

class FakeReportsRepository implements ReportsRepository {
  FakeReportsRepository(this._report);

  final PeriodReport _report;

  @override
  Future<PeriodReport> getPeriodReport({required DateTime from, required DateTime to}) async => _report;

  @override
  Future<CardSummary?> getCardSummary({required String cardId, required DateTime today}) async => null;
}

class FakeSyncRepository implements SyncRepository {
  @override
  Future<SyncStatus> getStatus() async => const SyncStatus(
        enabled: false,
        deviceId: 'dev',
        serverCursor: null,
        pendingCount: 0,
        lastSyncAt: null,
      );

  @override
  Future<SyncRunResult> runSync({bool force = false}) async =>
      const SyncRunResult(success: true, pushedCount: 0, pulledCount: 0);

  @override
  Future<void> setSyncEnabled(bool enabled) async {}

  @override
  Stream<List<PendingOperation>> watchPendingOperations() => Stream<List<PendingOperation>>.value(const <PendingOperation>[]);
}
