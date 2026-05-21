import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/widgets/async_value_view.dart';
import '../../../core/widgets/empty_state.dart';
import '../../cards/application/cards_providers.dart';
import '../../cards/domain/card_model.dart';
import '../application/transactions_providers.dart';
import '../domain/payment_mode.dart';
import '../domain/transaction_model.dart';

class TransactionsScreen extends ConsumerWidget {
  const TransactionsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final TransactionFilter filter = ref.watch(transactionFilterProvider);
    final AsyncValue<List<TransactionModel>> txns = ref.watch(filteredTransactionsProvider);
    final AsyncValue<List<CardModel>> cards = ref.watch(cardsStreamProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Transactions')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/transactions/new'),
        icon: const Icon(Icons.add),
        label: const Text('Add'),
      ),
      body: Column(
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.all(12),
            child: Wrap(
              spacing: 8,
              runSpacing: 8,
              children: <Widget>[
                ChoiceChip(
                  label: const Text('All modes'),
                  selected: filter.mode == null,
                  onSelected: (_) => ref
                      .read(transactionFilterProvider.notifier)
                      .state = const TransactionFilter(),
                ),
                for (final PaymentMode mode in PaymentMode.values)
                  ChoiceChip(
                    label: Text(mode.name.toUpperCase()),
                    selected: filter.mode == mode,
                    onSelected: (_) => ref
                        .read(transactionFilterProvider.notifier)
                        .state = TransactionFilter(mode: mode),
                  ),
              ],
            ),
          ),
          cards.when(
            data: (List<CardModel> data) {
              if (filter.mode != PaymentMode.card || data.isEmpty) {
                return const SizedBox.shrink();
              }
              return SizedBox(
                height: 52,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  children: <Widget>[
                    ChoiceChip(
                      label: const Text('All cards'),
                      selected: filter.cardId == null,
                      onSelected: (_) => ref
                          .read(transactionFilterProvider.notifier)
                          .state = filter.copyWith(clearCard: true),
                    ),
                    const SizedBox(width: 8),
                    for (final CardModel card in data)
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ChoiceChip(
                          label: Text(card.cardName),
                          selected: filter.cardId == card.id,
                          onSelected: (_) => ref
                              .read(transactionFilterProvider.notifier)
                              .state = filter.copyWith(cardId: card.id),
                        ),
                      ),
                  ],
                ),
              );
            },
            loading: () => const SizedBox.shrink(),
            error: (_, __) => const SizedBox.shrink(),
          ),
          Expanded(
            child: AsyncValueView<List<TransactionModel>>(
              value: txns,
              onRetry: () => ref.invalidate(filteredTransactionsProvider),
              isEmpty: (List<TransactionModel> value) => value.isEmpty,
              emptyBuilder: (_) => const EmptyState(
                title: 'No transactions',
                subtitle: 'Create your first transaction to populate this list.',
              ),
              data: (List<TransactionModel> data) {
                return ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: data.length,
                  itemBuilder: (BuildContext context, int index) {
                    final TransactionModel txn = data[index];
                    return Card(
                      child: ListTile(
                        title: Text(
                          '${txn.paymentMode.name.toUpperCase()} • ${formatCurrency(txn.finalAmount)}',
                        ),
                        subtitle: Text(
                          '${formatDate(txn.txnDate)}\n'
                          'Discount ${formatCurrency(txn.discountAmount)} • Cashback ${formatCurrency(txn.cashbackAmount)}\n'
                          '${txn.category ?? '-'} • ${txn.notes ?? '-'}',
                        ),
                        isThreeLine: true,
                        trailing: PopupMenuButton<String>(
                          onSelected: (String selected) async {
                            if (selected == 'edit') {
                              context.push('/transactions/${txn.id}/edit');
                            } else if (selected == 'delete') {
                              await ref.read(transactionsRepositoryProvider).deleteById(txn.id);
                            }
                          },
                          itemBuilder: (_) => const <PopupMenuEntry<String>>[
                            PopupMenuItem<String>(value: 'edit', child: Text('Edit')),
                            PopupMenuItem<String>(value: 'delete', child: Text('Delete')),
                          ],
                        ),
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
