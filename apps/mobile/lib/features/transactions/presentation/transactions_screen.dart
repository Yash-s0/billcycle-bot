import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/widgets/async_value_view.dart';
import '../../../core/widgets/empty_state.dart';
import '../../../core/widgets/ui_primitives.dart';
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
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 6),
            child: Align(
              alignment: Alignment.centerLeft,
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                children: <Widget>[
                  ChoiceChip(
                    label: const Text('All modes'),
                    selected: filter.mode == null,
                    onSelected: (_) => ref.read(transactionFilterProvider.notifier).state = const TransactionFilter(),
                  ),
                  for (final PaymentMode mode in PaymentMode.values)
                    ChoiceChip(
                      label: Text(mode.name.toUpperCase()),
                      selected: filter.mode == mode,
                      onSelected: (_) => ref.read(transactionFilterProvider.notifier).state = TransactionFilter(mode: mode),
                    ),
                ],
              ),
            ),
          ),
          cards.when(
            data: (List<CardModel> data) {
              if (filter.mode != PaymentMode.card || data.isEmpty) {
                return const SizedBox.shrink();
              }
              return SizedBox(
                height: 56,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  children: <Widget>[
                    ChoiceChip(
                      label: const Text('All cards'),
                      selected: filter.cardId == null,
                      onSelected: (_) => ref.read(transactionFilterProvider.notifier).state = filter.copyWith(clearCard: true),
                    ),
                    const SizedBox(width: 8),
                    for (final CardModel card in data)
                      Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: ChoiceChip(
                          label: Text(
                            card.cardName,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          selected: filter.cardId == card.id,
                          onSelected: (_) => ref.read(transactionFilterProvider.notifier).state = filter.copyWith(cardId: card.id),
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
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(14, 12, 10, 12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: <Widget>[
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: <Widget>[
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: <Widget>[
                                      Text(
                                        formatCurrency(txn.finalAmount),
                                        style: Theme.of(context).textTheme.titleLarge,
                                      ),
                                      const SizedBox(height: 2),
                                      Text(
                                        formatDate(txn.txnDate),
                                        style: Theme.of(context).textTheme.bodySmall,
                                      ),
                                    ],
                                  ),
                                ),
                                const SizedBox(width: 8),
                                UiStatusPill(label: txn.paymentMode.name.toUpperCase()),
                                PopupMenuButton<String>(
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
                              ],
                            ),
                            const SizedBox(height: 10),
                            Wrap(
                              spacing: 14,
                              runSpacing: 4,
                              children: <Widget>[
                                Text('Discount ${formatCurrency(txn.discountAmount)}'),
                                Text('Cashback ${formatCurrency(txn.cashbackAmount)}'),
                              ],
                            ),
                            if ((txn.category ?? '').isNotEmpty) ...<Widget>[
                              const SizedBox(height: 6),
                              Text(
                                txn.category!,
                                style: Theme.of(context).textTheme.titleSmall,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                            if ((txn.notes ?? '').isNotEmpty) ...<Widget>[
                              const SizedBox(height: 4),
                              Text(
                                txn.notes!,
                                style: Theme.of(context).textTheme.bodySmall,
                                maxLines: 3,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
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
