import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/widgets/async_value_view.dart';
import '../../../core/widgets/empty_state.dart';
import '../application/card_bill_providers.dart';
import '../domain/card_bill_pending_item.dart';

class CardBillsScreen extends ConsumerWidget {
  const CardBillsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<CardBillPendingItem>> items = ref.watch(cardBillPendingProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Card Bill Tracker')),
      body: AsyncValueView<List<CardBillPendingItem>>(
        value: items,
        onRetry: () => ref.invalidate(cardBillPendingProvider),
        isEmpty: (List<CardBillPendingItem> value) => value.isEmpty,
        emptyBuilder: (_) => const EmptyState(
          title: 'No cards',
          subtitle: 'Add a card to track billing cycle payments.',
        ),
        data: (List<CardBillPendingItem> value) {
          return ListView.builder(
            padding: const EdgeInsets.all(12),
            itemCount: value.length,
            itemBuilder: (BuildContext context, int index) {
              final CardBillPendingItem item = value[index];
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(item.cardLabel, style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 6),
                      Text('Cycle: ${formatDate(item.cycleStart)} → ${formatDate(item.cycleEnd)}'),
                      Text('Due: ${formatDate(item.dueDate)}'),
                      const SizedBox(height: 8),
                      Text('Billed: ${formatCurrency(item.billedAmount)}'),
                      Text('Paid: ${formatCurrency(item.paidAmount)}'),
                      Text('Pending: ${formatCurrency(item.pendingAmount)}'),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        children: <Widget>[
                          FilledButton(
                            onPressed: item.pendingAmount <= 0
                                ? null
                                : () async {
                                    await ref.read(cardBillRepositoryProvider).markPaid(
                                          item: item,
                                          amountPaid: item.pendingAmount,
                                          notes: 'Fully paid',
                                        );
                                  },
                            child: const Text('Mark fully paid'),
                          ),
                          OutlinedButton(
                            onPressed: item.pendingAmount <= 0
                                ? null
                                : () async {
                                    final TextEditingController controller =
                                        TextEditingController();
                                    final double? value = await showDialog<double>(
                                      context: context,
                                      builder: (BuildContext context) {
                                        return AlertDialog(
                                          title: const Text('Partial payment'),
                                          content: TextField(
                                            controller: controller,
                                            keyboardType: const TextInputType.numberWithOptions(decimal: true),
                                            decoration: const InputDecoration(labelText: 'Amount'),
                                          ),
                                          actions: <Widget>[
                                            TextButton(
                                              onPressed: () => Navigator.of(context).pop(),
                                              child: const Text('Cancel'),
                                            ),
                                            FilledButton(
                                              onPressed: () {
                                                Navigator.of(context).pop(
                                                  double.tryParse(controller.text.trim()),
                                                );
                                              },
                                              child: const Text('Save'),
                                            ),
                                          ],
                                        );
                                      },
                                    );
                                    if (value == null || value <= 0 || value > item.pendingAmount) {
                                      return;
                                    }
                                    await ref.read(cardBillRepositoryProvider).markPaid(
                                          item: item,
                                          amountPaid: value,
                                          notes: 'Partial payment',
                                        );
                                  },
                            child: const Text('Partial paid'),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
