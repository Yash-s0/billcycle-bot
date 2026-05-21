import 'package:intl/intl.dart';

DateTime _anchorDate(int year, int month, int day) {
  final DateTime first = DateTime.utc(year, month, 1);
  final int lastDay = DateTime.utc(year, month + 1, 0).day;
  final int safeDay = day.clamp(1, lastDay).toInt();
  return DateTime.utc(year, month, safeDay);
}

DateTime getNextDueDate({required int dueDay, required DateTime today}) {
  final DateTime now = DateTime.utc(today.year, today.month, today.day);
  final DateTime currentMonthDue = _anchorDate(now.year, now.month, dueDay);
  if (!currentMonthDue.isBefore(now)) {
    return currentMonthDue;
  }
  final DateTime nextMonth = DateTime.utc(now.year, now.month + 1, 1);
  return _anchorDate(nextMonth.year, nextMonth.month, dueDay);
}

({DateTime start, DateTime end}) getCurrentBillingCycle({
  required int billingDay,
  required DateTime today,
}) {
  final DateTime now = DateTime.utc(today.year, today.month, today.day);
  final DateTime currentAnchor = _anchorDate(now.year, now.month, billingDay);
  final DateTime start = !now.isBefore(currentAnchor)
      ? currentAnchor
      : _anchorDate(DateTime.utc(now.year, now.month - 1, 1).year, DateTime.utc(now.year, now.month - 1, 1).month, billingDay);

  final DateTime nextCycleStart = _anchorDate(
    DateTime.utc(start.year, start.month + 1, 1).year,
    DateTime.utc(start.year, start.month + 1, 1).month,
    billingDay,
  );
  final DateTime end = nextCycleStart.subtract(const Duration(days: 1));

  return (start: start, end: end);
}

String asIsoDate(DateTime date) => DateFormat('yyyy-MM-dd').format(date.toUtc());
