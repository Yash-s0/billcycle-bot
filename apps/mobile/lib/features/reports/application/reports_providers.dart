import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../domain/report_models.dart';

class ReportRange {
  const ReportRange({
    required this.from,
    required this.to,
    required this.label,
  });

  final DateTime from;
  final DateTime to;
  final String label;

  static ReportRange today() {
    final DateTime now = DateTime.now().toUtc();
    final DateTime day = DateTime.utc(now.year, now.month, now.day);
    return ReportRange(from: day, to: day, label: 'Today');
  }

  static ReportRange weekly() {
    final DateTime now = DateTime.now().toUtc();
    final DateTime day = DateTime.utc(now.year, now.month, now.day);
    return ReportRange(
      from: day.subtract(const Duration(days: 6)),
      to: day,
      label: 'Last 7 days',
    );
  }

  static ReportRange monthly() {
    final DateTime now = DateTime.now().toUtc();
    final DateTime first = DateTime.utc(now.year, now.month, 1);
    final DateTime today = DateTime.utc(now.year, now.month, now.day);
    return ReportRange(from: first, to: today, label: 'Current month');
  }
}

final reportRangeProvider = StateProvider<ReportRange>((Ref ref) {
  return ReportRange.monthly();
});

final periodReportProvider = FutureProvider<PeriodReport>((Ref ref) {
  final ReportRange range = ref.watch(reportRangeProvider);
  return ref.watch(reportsRepositoryProvider).getPeriodReport(
        from: range.from,
        to: range.to,
      );
});
