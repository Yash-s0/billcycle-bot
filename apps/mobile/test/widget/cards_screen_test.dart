import 'package:billcycle_mobile/core/contracts/providers.dart';
import 'package:billcycle_mobile/features/cards/domain/card_model.dart';
import 'package:billcycle_mobile/features/cards/presentation/cards_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../fixtures/fake_cards_repository.dart';

void main() {
  testWidgets('renders cards from repository stream', (WidgetTester tester) async {
    final CardModel card = CardModel(
      id: '1',
      bankName: 'HDFC',
      cardName: 'Regalia',
      billingDay: 10,
      dueDay: 18,
      creditLimit: 200000,
      createdAt: DateTime.utc(2026, 1, 1),
      updatedAt: DateTime.utc(2026, 1, 1),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          cardsRepositoryProvider.overrideWithValue(FakeCardsRepository([card])),
        ],
        child: const MaterialApp(home: CardsScreen()),
      ),
    );

    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));

    expect(find.text('HDFC/Regalia'), findsOneWidget);
    expect(find.textContaining('Billing day 10'), findsOneWidget);
  });
}
