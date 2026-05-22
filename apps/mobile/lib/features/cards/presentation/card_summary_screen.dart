import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/widgets/async_value_view.dart';
import '../../../core/widgets/ui_primitives.dart';
import '../../reports/domain/report_models.dart';

class CardSummaryScreen extends ConsumerWidget {
  const CardSummaryScreen({
    super.key,
    required this.cardId,
  });

  final String cardId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final provider = FutureProvider<CardSummary?>((Ref ref) {
      return ref.watch(reportsRepositoryProvider).getCardSummary(
            cardId: cardId,
            today: DateTime.now().toUtc(),
          );
    });

    final AsyncValue<CardSummary?> summary = ref.watch(provider);

    return Scaffold(
      appBar: AppBar(title: const Text('Card summary')),
      body: AsyncValueView<CardSummary?>(
        value: summary,
        onRetry: () => ref.invalidate(provider),
        isEmpty: (CardSummary? value) => value == null,
        data: (CardSummary? value) {
          if (value == null) {
            return const Center(child: Text('Card not found'));
          }
          return ListView(
            padding: const EdgeInsets.all(16),
            children: <Widget>[
              UiSectionCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(value.cardLabel, style: Theme.of(context).textTheme.headlineSmall),
                    const SizedBox(height: 8),
                    Text(
                      'Cycle: ${formatDate(value.cycleStart)} → ${formatDate(value.cycleEnd)}',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              UiMetricCard(title: 'Total billed', value: formatCurrency(value.totalSpend)),
              UiMetricCard(title: 'Discounts', value: formatCurrency(value.totalDiscount)),
              UiMetricCard(title: 'Cashback', value: formatCurrency(value.totalCashback)),
              UiMetricCard(
                title: 'Pending receivables',
                value: formatCurrency(value.pendingReceivables),
              ),
              UiMetricCard(title: 'Upcoming due date', value: formatDate(value.upcomingDueDate)),
            ],
          );
        },
      ),
    );
  }
}
