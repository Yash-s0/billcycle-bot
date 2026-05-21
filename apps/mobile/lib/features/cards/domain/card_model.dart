class CardModel {
  const CardModel({
    required this.id,
    required this.bankName,
    required this.cardName,
    required this.billingDay,
    required this.dueDay,
    this.creditLimit,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String bankName;
  final String cardName;
  final int billingDay;
  final int dueDay;
  final double? creditLimit;
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;

  String get label => '$bankName/$cardName';

  CardModel copyWith({
    String? id,
    String? bankName,
    String? cardName,
    int? billingDay,
    int? dueDay,
    double? creditLimit,
    String? notes,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return CardModel(
      id: id ?? this.id,
      bankName: bankName ?? this.bankName,
      cardName: cardName ?? this.cardName,
      billingDay: billingDay ?? this.billingDay,
      dueDay: dueDay ?? this.dueDay,
      creditLimit: creditLimit ?? this.creditLimit,
      notes: notes ?? this.notes,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  Map<String, Object?> toMap() {
    return {
      'id': id,
      'bank_name': bankName,
      'card_name': cardName,
      'billing_day': billingDay,
      'due_day': dueDay,
      'credit_limit': creditLimit,
      'notes': notes,
      'created_at': createdAt.toUtc().toIso8601String(),
      'updated_at': updatedAt.toUtc().toIso8601String(),
    };
  }

  factory CardModel.fromMap(Map<String, Object?> map) {
    return CardModel(
      id: map['id']! as String,
      bankName: map['bank_name']! as String,
      cardName: map['card_name']! as String,
      billingDay: map['billing_day']! as int,
      dueDay: map['due_day']! as int,
      creditLimit: (map['credit_limit'] as num?)?.toDouble(),
      notes: map['notes'] as String?,
      createdAt: DateTime.parse(map['created_at']! as String).toUtc(),
      updatedAt: DateTime.parse(map['updated_at']! as String).toUtc(),
    );
  }
}
