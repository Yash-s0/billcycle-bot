import 'package:billcycle_mobile/core/contracts/providers.dart';
import 'package:billcycle_mobile/features/cards/domain/card_model.dart';
import 'package:billcycle_mobile/features/notifications/domain/notification_event.dart';
import 'package:billcycle_mobile/features/notifications/presentation/notifications_screen.dart';
import 'package:billcycle_mobile/features/receivables/domain/person_pending_summary.dart';
import 'package:billcycle_mobile/features/receivables/presentation/receivables_screen.dart';
import 'package:billcycle_mobile/features/reports/domain/report_models.dart';
import 'package:billcycle_mobile/features/reports/presentation/reports_screen.dart';
import 'package:billcycle_mobile/features/transactions/domain/payment_mode.dart';
import 'package:billcycle_mobile/features/transactions/domain/reimbursement_status.dart';
import 'package:billcycle_mobile/features/transactions/domain/transaction_model.dart';
import 'package:billcycle_mobile/features/transactions/presentation/transactions_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../fixtures/fake_cards_repository.dart';
import '../fixtures/fake_ui_repositories.dart';

void main() {
  Future<void> pumpNarrow(WidgetTester tester, Widget child, {List<Override> overrides = const <Override>[]}) async {
    await tester.binding.setSurfaceSize(const Size(320, 780));
    await tester.pumpWidget(
      ProviderScope(
        overrides: overrides,
        child: MaterialApp(
          home: MediaQuery(
            data: const MediaQueryData(textScaler: TextScaler.linear(1.3)),
            child: child,
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));
  }

  testWidgets('transactions screen handles long content on narrow width', (WidgetTester tester) async {
    final txn = TransactionModel(
      id: 'tx1',
      cardId: 'c1',
      paymentMode: PaymentMode.card,
      amount: 15499,
      discountAmount: 499,
      cashbackAmount: 100,
      finalAmount: 15000,
      txnDate: DateTime.utc(2026, 1, 1),
      isForSomeoneElse: false,
      personId: null,
      reimbursementStatus: ReimbursementStatus.own,
      category: 'Very long electronics shopping category for overflow testing',
      notes: 'This is a very long note intended to validate wrapping and truncation behaviour in transaction list cards.',
      createdAt: DateTime.utc(2026, 1, 1),
      updatedAt: DateTime.utc(2026, 1, 1),
    );

    await pumpNarrow(
      tester,
      const TransactionsScreen(),
      overrides: <Override>[
        transactionsRepositoryProvider.overrideWithValue(FakeTransactionsRepository(<TransactionModel>[txn])),
        cardsRepositoryProvider.overrideWithValue(
          FakeCardsRepository(<CardModel>[
            CardModel(
              id: 'c1',
              bankName: 'HDFC',
              cardName: 'Regalia 1234',
              billingDay: 10,
              dueDay: 18,
              createdAt: DateTime.utc(2026, 1, 1),
              updatedAt: DateTime.utc(2026, 1, 1),
            ),
          ]),
        ),
      ],
    );

    expect(find.textContaining('₹'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('notifications screen handles long body text on narrow width', (WidgetTester tester) async {
    final item = NotificationEvent(
      id: 'n1',
      type: 'info',
      title: 'Long notification title for render test and clipping protection',
      body: 'Long notification body text to ensure the list tile subtitle does not overflow on small devices and larger text scale.',
      payload: '{}',
      createdAt: DateTime.utc(2026, 1, 1),
    );

    await pumpNarrow(
      tester,
      const NotificationsScreen(),
      overrides: <Override>[
        remindersRepositoryProvider.overrideWithValue(FakeRemindersRepository(<NotificationEvent>[item])),
      ],
    );

    expect(find.textContaining('Long notification'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('receivables screen handles long names and values on narrow width', (WidgetTester tester) async {
    await pumpNarrow(
      tester,
      const ReceivablesScreen(),
      overrides: <Override>[
        receivablesRepositoryProvider.overrideWithValue(
          FakeReceivablesRepository(
            <PersonPendingSummary>[
              const PersonPendingSummary(
                personId: 'p1',
                personName: 'Very Long Person Name To Validate Wrapping Safety In Receivables View',
                totalAmount: 10000,
                pendingAmount: 8500,
                cashbackAmount: 200,
                transactionCount: 12,
              ),
            ],
          ),
        ),
      ],
    );

    expect(find.textContaining('Very Long Person Name'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('reports screen handles metrics and rows on narrow width', (WidgetTester tester) async {
    await pumpNarrow(
      tester,
      const ReportsScreen(),
      overrides: <Override>[
        reportsRepositoryProvider.overrideWithValue(
          FakeReportsRepository(
            PeriodReport(
              from: DateTime.utc(2026, 1, 1),
              to: DateTime.utc(2026, 1, 30),
              totalSpent: 100000,
              totalDiscount: 5000,
              totalCashback: 1200,
              cardBillToRepay: 62000,
              amountOwedByOthers: 7000,
              topNotes: const <MapEntry<String, double>>[
                MapEntry<String, double>('Long shopping note for testing line wrapping behavior', 9999),
              ],
              breakdown: const <CardBreakdownItem>[
                CardBreakdownItem(
                  label: 'Card One Long Name For Display',
                  totalBilled: 50000,
                  totalDiscount: 3000,
                  totalCashback: 800,
                  effectiveNet: 46200,
                ),
              ],
            ),
          ),
        ),
      ],
    );

    expect(find.text('Reports'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
