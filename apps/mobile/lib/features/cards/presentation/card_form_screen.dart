import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../../core/contracts/providers.dart';
import '../../../core/validation/validators.dart';
import '../../../core/widgets/ui_primitives.dart';
import '../data/card_scan_service.dart';
import 'card_scanner_screen.dart';
import '../domain/card_scan_result.dart';
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
  bool _scanning = false;
  CardModel? _editing;
  final CardScanService _cardScanService = CardScanService();

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
    _cardScanService.dispose();
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
                          child: OutlinedButton.icon(
                            onPressed: _scanning ? null : _scanFromInAppCamera,
                            icon: _scanning
                                ? const SizedBox(
                                    width: 16,
                                    height: 16,
                                    child: CircularProgressIndicator(strokeWidth: 2),
                                  )
                                : const Icon(Icons.document_scanner_outlined),
                            label: Text(_scanning ? 'Scanning...' : 'Scan card'),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _scanning ? null : () => _scanCardAndAutofill(fromGallery: true),
                            icon: const Icon(Icons.photo_library_outlined),
                            label: const Text('Gallery'),
                          ),
                        ),
                      ],
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

  Future<void> _scanCardAndAutofill({required bool fromGallery}) async {
    setState(() {
      _scanning = true;
    });

    try {
      final CardScanParseResult? parsed = fromGallery ? await _cardScanService.scanFromGallery() : null;
      if (!mounted) {
        return;
      }
      if (parsed == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(fromGallery ? 'No image selected.' : 'Card scan cancelled.')),
        );
        return;
      }

      final CardScanConfirmedResult? confirmed = await _confirmParsedResult(parsed);
      if (!mounted || confirmed == null) {
        return;
      }
      _applyConfirmedResult(confirmed);
    } catch (_) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Card scan failed. Please try again.')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _scanning = false;
        });
      }
    }
  }

  Future<void> _scanFromInAppCamera() async {
    if (_scanning) {
      return;
    }

    setState(() {
      _scanning = true;
    });

    try {
      final CardScanConfirmedResult? result = await Navigator.of(context).push<CardScanConfirmedResult>(
        MaterialPageRoute<CardScanConfirmedResult>(
          builder: (_) => const CardScannerScreen(),
        ),
      );

      if (!mounted) {
        return;
      }
      if (result == null) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Scan cancelled.')),
        );
        return;
      }

      _applyConfirmedResult(result);
    } catch (_) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Failed to open scanner. Please try again.')),
      );
    } finally {
      if (mounted) {
        setState(() {
          _scanning = false;
        });
      }
    }
  }

  void _applyConfirmedResult(CardScanConfirmedResult confirmed) {
    bool updatedAny = false;
    if (_bank.text.trim().isEmpty && confirmed.bankName.trim().isNotEmpty) {
      _bank.text = confirmed.bankName.trim();
      updatedAny = true;
    }

    if (confirmed.last4.trim().length == 4) {
      final String current = _name.text.trim();
      if (current.isEmpty) {
        _name.text = 'Card ${confirmed.last4.trim()}';
        updatedAny = true;
      } else if (!current.contains(confirmed.last4.trim())) {
        _name.text = '$current ${confirmed.last4.trim()}';
        updatedAny = true;
      }
    }

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(
          updatedAny
              ? 'Scanned card details applied.'
              : 'Details confirmed. Fields were already filled.',
        ),
      ),
    );
  }

  Future<CardScanConfirmedResult?> _confirmParsedResult(CardScanParseResult parsed) async {
    final TextEditingController bankController = TextEditingController(text: parsed.suggestedBank ?? '');
    final TextEditingController last4Controller = TextEditingController(text: parsed.suggestedLast4 ?? '');

    final bool? apply = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (BuildContext context) {
        final bool hasSuggestions = parsed.hasAnySuggestion;
        final String guidance = hasSuggestions
            ? 'Verify or edit detected details before applying.'
            : 'Could not confidently detect details. You can edit and apply manually.';
        return Padding(
          padding: EdgeInsets.only(
            left: 16,
            right: 16,
            top: 8,
            bottom: MediaQuery.of(context).viewInsets.bottom + 16,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text('Confirm card details', style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Text(guidance),
              const SizedBox(height: 12),
              TextFormField(
                controller: bankController,
                decoration: const InputDecoration(labelText: 'Bank name'),
              ),
              const SizedBox(height: 10),
              TextFormField(
                controller: last4Controller,
                keyboardType: TextInputType.number,
                maxLength: 4,
                decoration: const InputDecoration(labelText: 'Card last 4 digits'),
              ),
              const SizedBox(height: 8),
              Text(
                parsed.ocrSnippet.isEmpty ? 'No OCR text available.' : 'OCR: ${parsed.ocrSnippet}',
                style: Theme.of(context).textTheme.bodySmall,
                maxLines: 4,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 14),
              Row(
                children: <Widget>[
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.of(context).pop(false),
                      child: const Text('Retake'),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: FilledButton(
                      onPressed: () {
                        final String bank = bankController.text.trim();
                        final String last4 = last4Controller.text.trim();
                        if (bank.isEmpty || last4.length != 4) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(content: Text('Enter valid bank name and 4-digit last4.')),
                          );
                          return;
                        }
                        Navigator.of(context).pop(true);
                      },
                      child: const Text('Use these details'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('Cancel'),
              ),
            ],
          ),
        );
      },
    );

    if (apply != true) {
      return null;
    }
    return CardScanConfirmedResult(
      bankName: bankController.text.trim(),
      last4: last4Controller.text.trim(),
      rawOcrText: parsed.ocrSnippet,
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
