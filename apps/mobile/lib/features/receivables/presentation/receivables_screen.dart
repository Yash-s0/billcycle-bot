import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/utils/formatters.dart';
import '../../../core/widgets/async_value_view.dart';
import '../../../core/widgets/empty_state.dart';
import '../application/receivables_providers.dart';
import '../domain/person_pending_summary.dart';

class ReceivablesScreen extends ConsumerWidget {
  const ReceivablesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<PersonPendingSummary>> summary = ref.watch(receivablesProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Who owes me')),
      body: AsyncValueView<List<PersonPendingSummary>>(
        value: summary,
        onRetry: () => ref.invalidate(receivablesProvider),
        isEmpty: (List<PersonPendingSummary> value) => value.isEmpty,
        emptyBuilder: (_) => const EmptyState(
          title: 'No receivables',
          subtitle: 'Nobody owes you right now.',
        ),
        data: (List<PersonPendingSummary> value) {
          return ListView.builder(
            padding: const EdgeInsets.all(12),
            itemCount: value.length,
            itemBuilder: (BuildContext context, int index) {
              final PersonPendingSummary item = value[index];
              return Card(
                child: ListTile(
                  title: Text(item.personName),
                  subtitle: Text(
                    'Owes ${formatCurrency(item.pendingAmount)} '
                    '• Cashback ${formatCurrency(item.cashbackAmount)} '
                    '• Transactions ${item.transactionCount}',
                  ),
                  trailing: Text(formatCurrency(item.totalAmount)),
                ),
              );
            },
          );
        },
      ),
    );
  }
}
