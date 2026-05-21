import 'dart:async';
import 'dart:convert';

import 'package:uuid/uuid.dart';

import '../../features/transactions/domain/payment_mode.dart';
import '../../features/transactions/domain/reimbursement_status.dart';
import '../db/app_database.dart';
import '../db/map_utils.dart';
import '../db/table_names.dart';
import '../logging/app_logger.dart';
import '../sync/outbox_queue.dart';
import 'transaction_notification_channel.dart';

class TransactionNotificationIngestor {
  TransactionNotificationIngestor(this._database) : _outbox = OutboxQueue(_database);

  final AppDatabase _database;
  final OutboxQueue _outbox;
  final Uuid _uuid = const Uuid();
  StreamSubscription<Map<String, dynamic>>? _subscription;

  static const Set<String> _txnKeywords = <String>{
    'spent',
    'debited',
    'debit',
    'purchase',
    'transaction',
    'txn',
    'charged',
    'paid at',
    'pos',
  };

  static final RegExp _amountPattern = RegExp(
    r'(?:inr|rs\.?|₹)\s*([0-9][0-9,]*\.?[0-9]{0,2})',
    caseSensitive: false,
  );

  static final RegExp _last4Pattern = RegExp(
    r'(?:xx|x{2,}|\*{2,}|ending\s*|card\s*|a\/c\s*)(\d{4})',
    caseSensitive: false,
  );

  void start() {
    _subscription ??= TransactionNotificationChannel.notificationStream().listen(
      _handleNotification,
      onError: (Object error, StackTrace stackTrace) {
        AppLogger.error('Notification ingestion stream error', error: error, stackTrace: stackTrace);
      },
    );
  }

  Future<void> stop() async {
    await _subscription?.cancel();
    _subscription = null;
  }

  Future<void> _handleNotification(Map<String, dynamic> payload) async {
    final String title = (payload['title'] ?? '').toString().trim();
    final String body = (payload['text'] ?? '').toString().trim();
    if (body.isEmpty) {
      return;
    }

    final String combined = '$title $body'.toLowerCase();
    final bool looksTransactional = _txnKeywords.any(combined.contains);
    if (!looksTransactional) {
      return;
    }

    final String sourceKey = (payload['key'] ?? '').toString();
    if (sourceKey.isEmpty) {
      return;
    }

    final List<Map<String, Object?>> duplicateRows = await _database.query(
      'SELECT id FROM notification_ingestion_events WHERE source_key = ? LIMIT 1',
      params: <Object?>[sourceKey],
    );
    if (duplicateRows.isNotEmpty) {
      return;
    }

    final double? amount = _parseAmount(combined);
    final String? last4 = _parseLast4(combined);

    final DateTime now = DateTime.now().toUtc();
    final Map<String, Object?>? matchedCard = await _matchCard(combined, last4);
    String? transactionId;

    await _database.transaction(() async {
      if (amount != null && matchedCard != null) {
        transactionId = await _createTransaction(
          amount: amount,
          matchedCard: matchedCard,
          sourcePackage: (payload['package'] ?? '').toString(),
          title: title,
          body: body,
          createdAt: now,
        );
      }

      await _database.executeInsert(
        '''
        INSERT INTO notification_ingestion_events (
          id, source_key, package_name, title, body, amount, card_last4, transaction_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        params: <Object?>[
          _uuid.v4(),
          sourceKey,
          (payload['package'] ?? '').toString(),
          title,
          body,
          amount,
          last4,
          transactionId,
          now.toIso8601String(),
        ],
      );

      await _database.executeInsert(
        '''
        INSERT INTO notification_events (id, type, title, body, payload, created_at, read_at)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
        ''',
        params: <Object?>[
          _uuid.v4(),
          transactionId == null ? 'txn-detected-review' : 'txn-auto-added',
          transactionId == null ? 'Transaction detected for review' : 'Transaction auto-added',
          transactionId == null
              ? 'Could not auto-map card for message: $title'
              : 'Added ₹${amount!.toStringAsFixed(2)} to ${readString(matchedCard!, 'bank_name')}/${readString(matchedCard, 'card_name')}',
          jsonEncode(payload),
          now.toIso8601String(),
        ],
      );

      _database.notifyTables(
        <String>{
          TableNames.notificationIngestionEvents,
          TableNames.notificationEvents,
          TableNames.transactions,
          TableNames.pendingOperations,
        },
      );
    });
  }

  Future<String> _createTransaction({
    required double amount,
    required Map<String, Object?> matchedCard,
    required String sourcePackage,
    required String title,
    required String body,
    required DateTime createdAt,
  }) async {
    final String id = _uuid.v4();
    await _database.executeInsert(
      '''
      INSERT INTO transactions (
        id, card_id, payment_mode, amount, discount_amount, cashback_amount,
        final_amount, txn_date, is_for_someone_else, person_id,
        reimbursement_status, category, notes, created_at, updated_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ''',
      params: <Object?>[
        id,
        readString(matchedCard, 'id'),
        PaymentMode.card.value,
        amount,
        0,
        0,
        amount,
        createdAt.toIso8601String(),
        0,
        null,
        ReimbursementStatus.own.value,
        'Auto-captured',
        'Source: $sourcePackage\n$title\n$body',
        createdAt.toIso8601String(),
        createdAt.toIso8601String(),
      ],
    );

    await _outbox.enqueue(
      entityType: 'transaction',
      entityId: id,
      operationType: 'upsert',
      payload: <String, Object?>{
        'id': id,
        'card_id': readString(matchedCard, 'id'),
        'payment_mode': PaymentMode.card.value,
        'amount': amount,
        'discount_amount': 0,
        'cashback_amount': 0,
        'final_amount': amount,
        'txn_date': createdAt.toIso8601String(),
        'is_for_someone_else': 0,
        'person_id': null,
        'reimbursement_status': ReimbursementStatus.own.value,
        'category': 'Auto-captured',
        'notes': 'Source: $sourcePackage\n$title\n$body',
        'created_at': createdAt.toIso8601String(),
        'updated_at': createdAt.toIso8601String(),
      },
    );

    return id;
  }

  Future<Map<String, Object?>?> _matchCard(String combined, String? last4) async {
    final List<Map<String, Object?>> cards = await _database.query('SELECT * FROM cards');
    if (cards.isEmpty) {
      return null;
    }

    if (last4 != null) {
      for (final Map<String, Object?> card in cards) {
        final String name = readString(card, 'card_name').toLowerCase();
        final String notes = (card['notes'] as String? ?? '').toLowerCase();
        if (name.contains(last4) || notes.contains(last4)) {
          return card;
        }
      }
    }

    for (final Map<String, Object?> card in cards) {
      final String bank = readString(card, 'bank_name').toLowerCase();
      final String name = readString(card, 'card_name').toLowerCase();
      if (combined.contains(bank) || combined.contains(name)) {
        return card;
      }
    }

    return null;
  }

  double? _parseAmount(String text) {
    final Match? match = _amountPattern.firstMatch(text);
    if (match == null) {
      return null;
    }
    final String raw = (match.group(1) ?? '').replaceAll(',', '').trim();
    return double.tryParse(raw);
  }

  String? _parseLast4(String text) {
    final Match? match = _last4Pattern.firstMatch(text);
    return match?.group(1);
  }
}
