import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/utils/formatters.dart';
import '../../../core/widgets/async_value_view.dart';
import '../application/reports_providers.dart';
import '../domain/report_models.dart';

class ReportsScreen extends ConsumerWidget {
  const ReportsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ReportRange selected = ref.watch(reportRangeProvider);
    final AsyncValue<PeriodReport> report = ref.watch(periodReportProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Reports')),
      body: Column(
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.all(12),
            child: Wrap(
              spacing: 8,
              children: <Widget>[
                ChoiceChip(
                  label: const Text('Today'),
                  selected: selected.label == 'Today',
                  onSelected: (_) => ref.read(reportRangeProvider.notifier).state = ReportRange.today(),
                ),
                ChoiceChip(
                  label: const Text('Weekly'),
                  selected: selected.label == 'Last 7 days',
                  onSelected: (_) => ref.read(reportRangeProvider.notifier).state = ReportRange.weekly(),
                ),
                ChoiceChip(
                  label: const Text('Monthly'),
                  selected: selected.label == 'Current month',
                  onSelected: (_) => ref.read(reportRangeProvider.notifier).state = ReportRange.monthly(),
                ),
              ],
            ),
          ),
          Expanded(
            child: AsyncValueView<PeriodReport>(
              value: report,
              onRetry: () => ref.invalidate(periodReportProvider),
              data: (PeriodReport data) {
                return ListView(
                  padding: const EdgeInsets.all(16),
                  children: <Widget>[
                    Text(
                      '${formatDate(data.from)} to ${formatDate(data.to)}',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 12),
                    _metric('Total spent', formatCurrency(data.totalSpent)),
                    _metric('Total discounts', formatCurrency(data.totalDiscount)),
                    _metric('Total cashback', formatCurrency(data.totalCashback)),
                    _metric('Card bill to repay', formatCurrency(data.cardBillToRepay)),
                    _metric('Amount owed by others', formatCurrency(data.amountOwedByOthers)),
                    const SizedBox(height: 12),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text('Top notes', style: Theme.of(context).textTheme.titleMedium),
                            const SizedBox(height: 8),
                            if (data.topNotes.isEmpty)
                              const Text('No notes')
                            else
                              for (final MapEntry<String, double> item in data.topNotes)
                                Padding(
                                  padding: const EdgeInsets.only(bottom: 6),
                                  child: Text('${item.key}: ${formatCurrency(item.value)}'),
                                ),
                          ],
                        ),
                      ),
                    ),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(14),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Text('Spend breakdown', style: Theme.of(context).textTheme.titleMedium),
                            const SizedBox(height: 8),
                            if (data.breakdown.isEmpty)
                              const Text('No transactions')
                            else
                              for (final CardBreakdownItem item in data.breakdown)
                                Padding(
                                  padding: const EdgeInsets.only(bottom: 8),
                                  child: Text(
                                    '${item.label}: ${formatCurrency(item.totalBilled)} '
                                    '(discount ${formatCurrency(item.totalDiscount)}, '
                                    'cashback ${formatCurrency(item.totalCashback)}, '
                                    'net ${formatCurrency(item.effectiveNet)})',
                                  ),
                                ),
                          ],
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _metric(String label, String value) {
    return Card(
      child: ListTile(
        title: Text(label),
        trailing: Text(value),
      ),
    );
  }
}
