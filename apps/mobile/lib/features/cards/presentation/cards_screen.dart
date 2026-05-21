import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/utils/formatters.dart';
import '../../../core/widgets/async_value_view.dart';
import '../../../core/widgets/empty_state.dart';
import '../application/cards_providers.dart';
import '../domain/card_model.dart';

class CardsScreen extends ConsumerWidget {
  const CardsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final AsyncValue<List<CardModel>> cards = ref.watch(cardsStreamProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Cards')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push('/cards/new'),
        icon: const Icon(Icons.add),
        label: const Text('Add card'),
      ),
      body: AsyncValueView<List<CardModel>>(
        value: cards,
        onRetry: () => ref.invalidate(cardsStreamProvider),
        isEmpty: (List<CardModel> value) => value.isEmpty,
        emptyBuilder: (_) => const EmptyState(
          title: 'No cards yet',
          subtitle: 'Add a card to start tracking billing cycles and due dates.',
        ),
        data: (List<CardModel> value) {
          return ListView.builder(
            padding: const EdgeInsets.all(12),
            itemCount: value.length,
            itemBuilder: (BuildContext context, int index) {
              final CardModel card = value[index];
              return Card(
                child: ListTile(
                  title: Text(card.label),
                  subtitle: Text(
                    'Billing day ${card.billingDay} • Due day ${card.dueDay}\n'
                    'Limit: ${card.creditLimit == null ? '-' : formatCurrency(card.creditLimit!)}',
                  ),
                  isThreeLine: true,
                  onTap: () => context.push('/cards/${card.id}/summary'),
                  trailing: PopupMenuButton<String>(
                    onSelected: (String selected) async {
                      if (selected == 'edit') {
                        context.push('/cards/${card.id}/edit');
                        return;
                      }
                      if (selected == 'delete') {
                        final bool? confirmed = await showDialog<bool>(
                          context: context,
                          builder: (BuildContext context) {
                            return AlertDialog(
                              title: const Text('Delete card?'),
                              content: const Text(
                                'Deleting this card also impacts linked transactions.',
                              ),
                              actions: <Widget>[
                                TextButton(
                                  onPressed: () => Navigator.of(context).pop(false),
                                  child: const Text('Cancel'),
                                ),
                                FilledButton(
                                  onPressed: () => Navigator.of(context).pop(true),
                                  child: const Text('Delete'),
                                ),
                              ],
                            );
                          },
                        );

                        if (confirmed == true) {
                          await ref.read(cardsRepositoryProvider).deleteById(card.id);
                        }
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
    );
  }
}
