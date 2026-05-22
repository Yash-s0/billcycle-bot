import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/validation/validators.dart';
import '../../../core/widgets/ui_primitives.dart';
import '../domain/card_model.dart';

class CardFormScreen extends ConsumerStatefulWidget {
  const CardFormScreen({
    super.key,
    this.cardId,
  });

  final String? cardId;

  @override
  ConsumerState<CardFormScreen> createState() => _CardFormScreenState();
}

class _CardFormScreenState extends ConsumerState<CardFormScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _bank = TextEditingController();
  final TextEditingController _name = TextEditingController();
  final TextEditingController _billingDay = TextEditingController();
  final TextEditingController _dueDay = TextEditingController();
  final TextEditingController _limit = TextEditingController();
  final TextEditingController _notes = TextEditingController();

  bool _loading = false;
  CardModel? _editing;

  @override
  void initState() {
    super.initState();
    if (widget.cardId != null) {
      _loadCard();
    }
  }

  Future<void> _loadCard() async {
    final CardModel? card = await ref.read(cardsRepositoryProvider).findById(widget.cardId!);
    if (!mounted || card == null) {
      return;
    }
    setState(() {
      _editing = card;
      _bank.text = card.bankName;
      _name.text = card.cardName;
      _billingDay.text = card.billingDay.toString();
      _dueDay.text = card.dueDay.toString();
      _limit.text = card.creditLimit?.toString() ?? '';
      _notes.text = card.notes ?? '';
    });
  }

  @override
  void dispose() {
    _bank.dispose();
    _name.dispose();
    _billingDay.dispose();
    _dueDay.dispose();
    _limit.dispose();
    _notes.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      resizeToAvoidBottomInset: true,
      appBar: AppBar(title: Text(widget.cardId == null ? 'Add card' : 'Edit card')),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            children: <Widget>[
              UiSectionCard(
                title: 'Card details',
                child: Column(
                  children: <Widget>[
                    TextFormField(
                      controller: _bank,
                      decoration: const InputDecoration(
                        labelText: 'Bank name',
                        helperText: 'Example: HDFC, ICICI, Axis',
                      ),
                      validator: (String? value) => Validators.requiredText(value, field: 'Bank name'),
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _name,
                      decoration: const InputDecoration(
                        labelText: 'Card nickname',
                        helperText: 'Tip: include last 4 digits for notification matching',
                      ),
                      validator: (String? value) => Validators.requiredText(value, field: 'Card nickname'),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: <Widget>[
                        Expanded(
                          child: TextFormField(
                            controller: _billingDay,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(labelText: 'Billing day'),
                            validator: (String? value) => Validators.cardDay(value, field: 'Billing day'),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: TextFormField(
                            controller: _dueDay,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(labelText: 'Due day'),
                            validator: (String? value) => Validators.cardDay(value, field: 'Due day'),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _limit,
                      keyboardType: const TextInputType.numberWithOptions(decimal: true),
                      decoration: const InputDecoration(
                        labelText: 'Credit limit (optional)',
                        helperText: 'Leave empty if not applicable',
                      ),
                      validator: (String? value) => Validators.nonNegativeAmount(value, field: 'Credit limit'),
                    ),
                    const SizedBox(height: 12),
                    TextFormField(
                      controller: _notes,
                      maxLines: 3,
                      decoration: const InputDecoration(labelText: 'Notes (optional)'),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              FilledButton(
                onPressed: _loading ? null : _save,
                child: _loading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Save card'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) {
      return;
    }

    setState(() {
      _loading = true;
    });

    final DateTime now = DateTime.now().toUtc();
    final CardModel card = CardModel(
      id: _editing?.id ?? const Uuid().v4(),
      bankName: _bank.text.trim(),
      cardName: _name.text.trim(),
      billingDay: int.parse(_billingDay.text.trim()),
      dueDay: int.parse(_dueDay.text.trim()),
      creditLimit: _limit.text.trim().isEmpty ? null : double.parse(_limit.text.trim()),
      notes: _notes.text.trim().isEmpty ? null : _notes.text.trim(),
      createdAt: _editing?.createdAt ?? now,
      updatedAt: now,
    );

    await ref.read(cardsRepositoryProvider).upsert(card);

    if (!mounted) {
      return;
    }
    context.pop();
  }
}
