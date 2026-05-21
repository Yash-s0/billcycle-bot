import 'dart:async';

import 'package:billcycle_mobile/core/contracts/repositories.dart';
import 'package:billcycle_mobile/features/cards/domain/card_model.dart';

class FakeCardsRepository implements CardsRepository {
  FakeCardsRepository(this._seed);

  final List<CardModel> _seed;
  final StreamController<List<CardModel>> _controller = StreamController<List<CardModel>>.broadcast();

  @override
  Stream<List<CardModel>> watchCards() async* {
    yield List<CardModel>.from(_seed);
    yield* _controller.stream;
  }

  @override
  Future<CardModel?> findById(String id) async {
    for (final CardModel card in _seed) {
      if (card.id == id) {
        return card;
      }
    }
    return null;
  }

  @override
  Future<void> upsert(CardModel card) async {
    _seed.removeWhere((CardModel element) => element.id == card.id);
    _seed.add(card);
    _controller.add(List<CardModel>.from(_seed));
  }

  @override
  Future<void> deleteById(String id) async {
    _seed.removeWhere((CardModel element) => element.id == id);
    _controller.add(List<CardModel>.from(_seed));
  }
}
