import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/db/table_names.dart';
import '../../../core/validation/validators.dart';
import '../../cards/application/cards_providers.dart';
import '../../cards/domain/card_model.dart';
import '../domain/payment_mode.dart';
import '../domain/reimbursement_status.dart';
import '../domain/transaction_model.dart';

class TransactionFormScreen extends ConsumerStatefulWidget {
  const TransactionFormScreen({
    super.key,
    this.transactionId,
  });

  final String? transactionId;

  @override
  ConsumerState<TransactionFormScreen> createState() => _TransactionFormScreenState();
}

class _TransactionFormScreenState extends ConsumerState<TransactionFormScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _amount = TextEditingController();
  final TextEditingController _discount = TextEditingController(text: '0');
  final TextEditingController _cashback = TextEditingController(text: '0');
  final TextEditingController _date = TextEditingController();
  final TextEditingController _category = TextEditingController();
  final TextEditingController _notes = TextEditingController();
  final TextEditingController _personName = TextEditingController();

  PaymentMode _mode = PaymentMode.card;
  String? _cardId;
  bool _forSomeoneElse = false;
  bool _paidBack = false;
  bool _loading = false;
  TransactionModel? _editing;

  @override
  void initState() {
    super.initState();
    _date.text = DateTime.now().toUtc().toIso8601String().split('T').first;
    if (widget.transactionId != null) {
      _loadTransaction();
    }
  }

  Future<void> _loadTransaction() async {
    final TransactionModel? txn = await ref
        .read(transactionsRepositoryProvider)
        .findById(widget.transactionId!);
    if (!mounted || txn == null) {
      return;
    }
    setState(() {
      _editing = txn;
      _mode = txn.paymentMode;
      _cardId = txn.cardId;
      _amount.text = txn.amount.toString();
      _discount.text = txn.discountAmount.toString();
      _cashback.text = txn.cashbackAmount.toString();
      _date.text = txn.txnDate.toIso8601String().split('T').first;
      _category.text = txn.category ?? '';
      _notes.text = txn.notes ?? '';
      _forSomeoneElse = txn.isForSomeoneElse;
      _paidBack = txn.reimbursementStatus == ReimbursementStatus.paid;
    });
  }

  @override
  void dispose() {
    _amount.dispose();
    _discount.dispose();
    _cashback.dispose();
    _date.dispose();
    _category.dispose();
    _notes.dispose();
    _personName.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final AsyncValue<List<CardModel>> cards = ref.watch(cardsStreamProvider);

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.transactionId == null ? 'Add transaction' : 'Edit transaction'),
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: <Widget>[
            DropdownButtonFormField<PaymentMode>(
              initialValue: _mode,
              items: PaymentMode.values
                  .map(
                    (PaymentMode mode) => DropdownMenuItem<PaymentMode>(
                      value: mode,
                      child: Text(mode.name.toUpperCase()),
                    ),
                  )
                  .toList(growable: false),
              onChanged: (PaymentMode? mode) {
                if (mode == null) {
                  return;
                }
                setState(() {
                  _mode = mode;
                  if (_mode != PaymentMode.card) {
                    _cardId = null;
                  }
                });
              },
              decoration: const InputDecoration(labelText: 'Payment mode'),
            ),
            const SizedBox(height: 12),
            if (_mode == PaymentMode.card)
              cards.when(
                data: (List<CardModel> data) {
                  return DropdownButtonFormField<String>(
                    initialValue: _cardId,
                    items: data
                        .map(
                          (CardModel card) => DropdownMenuItem<String>(
                            value: card.id,
                            child: Text(card.label),
                          ),
                        )
                        .toList(growable: false),
                    onChanged: (String? value) => setState(() => _cardId = value),
                    validator: (String? value) => value == null ? 'Select a card' : null,
                    decoration: const InputDecoration(labelText: 'Card'),
                  );
                },
                loading: () => const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: LinearProgressIndicator(),
                ),
                error: (_, __) => const Text('Unable to load cards'),
              ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _amount,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(labelText: 'Amount'),
              validator: (String? value) => Validators.positiveAmount(value),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _discount,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(labelText: 'Discount'),
              validator: (String? value) => Validators.nonNegativeAmount(value, field: 'Discount'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _cashback,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(labelText: 'Cashback'),
              validator: (String? value) => Validators.nonNegativeAmount(value, field: 'Cashback'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _date,
              decoration: const InputDecoration(labelText: 'Date (YYYY-MM-DD)'),
              validator: (String? value) {
                if (value == null || value.trim().isEmpty) {
                  return 'Date is required';
                }
                return DateTime.tryParse(value.trim()) == null ? 'Invalid date' : null;
              },
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _category,
              decoration: const InputDecoration(labelText: 'Category (optional)'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _notes,
              maxLines: 3,
              decoration: const InputDecoration(labelText: 'Notes (optional)'),
            ),
            const SizedBox(height: 12),
            SwitchListTile(
              value: _forSomeoneElse,
              onChanged: (bool value) => setState(() => _forSomeoneElse = value),
              title: const Text('For someone else'),
            ),
            if (_forSomeoneElse) ...<Widget>[
              TextFormField(
                controller: _personName,
                decoration: const InputDecoration(labelText: 'Person name'),
                validator: (String? value) => _forSomeoneElse
                    ? Validators.requiredText(value, field: 'Person name')
                    : null,
              ),
              SwitchListTile(
                value: _paidBack,
                onChanged: (bool value) => setState(() => _paidBack = value),
                title: const Text('Already paid back'),
              ),
            ],
            const SizedBox(height: 20),
            FilledButton(
              onPressed: _loading ? null : _save,
              child: _loading
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Save transaction'),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    final double amount = double.parse(_amount.text.trim());
    final double discount = _discount.text.trim().isEmpty ? 0 : double.parse(_discount.text.trim());
    final double cashback = _cashback.text.trim().isEmpty ? 0 : double.parse(_cashback.text.trim());

    final String? validationError = Validators.transactionRules(
      amount: amount,
      discount: discount,
      cashback: cashback,
      paymentMode: _mode,
      cardId: _cardId,
      isForSomeoneElse: _forSomeoneElse,
      personName: _personName.text,
    );

    if (validationError != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(validationError)));
      return;
    }

    setState(() {
      _loading = true;
    });

    final DateTime now = DateTime.now().toUtc();
    final DateTime date = DateTime.parse(_date.text.trim()).toUtc();
    final double finalAmount = amount - discount;

    String? personId;
    if (_forSomeoneElse) {
      final personName = _personName.text.trim();
      final db = ref.read(appDatabaseProvider);
      final existing = await db.query(
        'SELECT id FROM people WHERE lower(name) = lower(?) LIMIT 1',
        params: <Object?>[personName],
      );
      if (existing.isNotEmpty) {
        personId = existing.first['id']! as String;
      } else {
        personId = const Uuid().v4();
        await db.executeInsert(
          'INSERT INTO people (id, name, phone, created_at) VALUES (?, ?, NULL, ?)',
          params: <Object?>[personId, personName, now.toIso8601String()],
          table: TableNames.people,
        );
      }
    }

    final TransactionModel txn = TransactionModel(
      id: _editing?.id ?? const Uuid().v4(),
      cardId: _mode == PaymentMode.card ? _cardId : null,
      paymentMode: _mode,
      amount: amount,
      discountAmount: discount,
      cashbackAmount: cashback,
      finalAmount: finalAmount,
      txnDate: date,
      isForSomeoneElse: _forSomeoneElse,
      personId: personId,
      reimbursementStatus: !_forSomeoneElse
          ? ReimbursementStatus.own
          : (_paidBack ? ReimbursementStatus.paid : ReimbursementStatus.pending),
      category: _category.text.trim().isEmpty ? null : _category.text.trim(),
      notes: _notes.text.trim().isEmpty ? null : _notes.text.trim(),
      createdAt: _editing?.createdAt ?? now,
      updatedAt: now,
    );

    await ref.read(transactionsRepositoryProvider).upsert(txn);

    if (_forSomeoneElse && _paidBack && personId != null && txn.recoverableAmount > 0) {
      await ref.read(appDatabaseProvider).executeInsert(
        '''
        INSERT INTO payments (id, transaction_id, person_id, amount_paid, paid_at, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ''',
        params: <Object?>[
          const Uuid().v4(),
          txn.id,
          personId,
          txn.recoverableAmount,
          now.toIso8601String(),
          'Marked as paid at transaction save',
        ],
        table: TableNames.payments,
      );
    }

    if (!mounted) {
      return;
    }
    context.pop();
  }
}
