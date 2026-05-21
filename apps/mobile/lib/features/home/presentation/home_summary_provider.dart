import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../../reports/domain/report_models.dart';

class HomeSummary {
  const HomeSummary({
    required this.totalSpentThisMonth,
    required this.cardBillToRepay,
    required this.pendingReceivables,
    required this.pendingSyncOperations,
    required this.unreadNotifications,
  });

  final double totalSpentThisMonth;
  final double cardBillToRepay;
  final double pendingReceivables;
  final int pendingSyncOperations;
  final int unreadNotifications;
}

final homeSummaryProvider = FutureProvider<HomeSummary>((Ref ref) async {
  final DateTime now = DateTime.now().toUtc();
  final DateTime monthStart = DateTime.utc(now.year, now.month, 1);
  final DateTime today = DateTime.utc(now.year, now.month, now.day);

  final PeriodReport report = await ref
      .watch(reportsRepositoryProvider)
      .getPeriodReport(from: monthStart, to: today);

  final List<Map<String, Object?>> syncCountRows = await ref
      .watch(appDatabaseProvider)
      .query('SELECT COUNT(*) AS count FROM pending_operations');
  final int syncCount = (syncCountRows.first['count'] as num?)?.toInt() ?? 0;

  final List<Map<String, Object?>> notificationRows = await ref
      .watch(appDatabaseProvider)
      .query('SELECT COUNT(*) AS count FROM notification_events WHERE read_at IS NULL');
  final int unread = (notificationRows.first['count'] as num?)?.toInt() ?? 0;

  return HomeSummary(
    totalSpentThisMonth: report.totalSpent,
    cardBillToRepay: report.cardBillToRepay,
    pendingReceivables: report.amountOwedByOthers,
    pendingSyncOperations: syncCount,
    unreadNotifications: unread,
  );
});
