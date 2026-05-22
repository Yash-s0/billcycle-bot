import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/utils/formatters.dart';
import '../../../core/widgets/async_value_view.dart';
import '../../../core/widgets/ui_primitives.dart';
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
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 6),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
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
                    UiMetricCard(title: 'Total spent', value: formatCurrency(data.totalSpent)),
                    UiMetricCard(title: 'Total discounts', value: formatCurrency(data.totalDiscount)),
                    UiMetricCard(title: 'Total cashback', value: formatCurrency(data.totalCashback)),
                    UiMetricCard(title: 'Card bill to repay', value: formatCurrency(data.cardBillToRepay)),
                    UiMetricCard(title: 'Amount owed by others', value: formatCurrency(data.amountOwedByOthers)),
                    const SizedBox(height: 8),
                    UiSectionCard(
                      title: 'Top notes',
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          if (data.topNotes.isEmpty)
                            const Text('No notes')
                          else
                            for (final MapEntry<String, double> item in data.topNotes)
                              UiKeyValueRow(label: item.key, value: formatCurrency(item.value)),
                        ],
                      ),
                    ),
                    UiSectionCard(
                      title: 'Spend breakdown',
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          if (data.breakdown.isEmpty)
                            const Text('No transactions')
                          else
                            for (final CardBreakdownItem item in data.breakdown)
                              Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  Text(item.label, style: Theme.of(context).textTheme.titleSmall),
                                  const SizedBox(height: 4),
                                  UiKeyValueRow(label: 'Billed', value: formatCurrency(item.totalBilled)),
                                  UiKeyValueRow(label: 'Discount', value: formatCurrency(item.totalDiscount)),
                                  UiKeyValueRow(label: 'Cashback', value: formatCurrency(item.totalCashback)),
                                  UiKeyValueRow(label: 'Net', value: formatCurrency(item.effectiveNet)),
                                  const Divider(height: 18),
                                ],
                              ),
                        ],
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
}
