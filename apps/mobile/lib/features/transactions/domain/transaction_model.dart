import 'payment_mode.dart';
import 'reimbursement_status.dart';

class TransactionModel {
  const TransactionModel({
    required this.id,
    this.cardId,
    required this.paymentMode,
    required this.amount,
    required this.discountAmount,
    required this.cashbackAmount,
    required this.finalAmount,
    required this.txnDate,
    required this.isForSomeoneElse,
    this.personId,
    required this.reimbursementStatus,
    this.category,
    this.notes,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String? cardId;
  final PaymentMode paymentMode;
  final double amount;
  final double discountAmount;
  final double cashbackAmount;
  final double finalAmount;
  final DateTime txnDate;
  final bool isForSomeoneElse;
  final String? personId;
  final ReimbursementStatus reimbursementStatus;
  final String? category;
  final String? notes;
  final DateTime createdAt;
  final DateTime updatedAt;

  double get recoverableAmount => finalAmount - cashbackAmount;

  Map<String, Object?> toMap() {
    return {
      'id': id,
      'card_id': cardId,
      'payment_mode': paymentMode.value,
      'amount': amount,
      'discount_amount': discountAmount,
      'cashback_amount': cashbackAmount,
      'final_amount': finalAmount,
      'txn_date': txnDate.toUtc().toIso8601String(),
      'is_for_someone_else': isForSomeoneElse ? 1 : 0,
      'person_id': personId,
      'reimbursement_status': reimbursementStatus.value,
      'category': category,
      'notes': notes,
      'created_at': createdAt.toUtc().toIso8601String(),
      'updated_at': updatedAt.toUtc().toIso8601String(),
    };
  }

  factory TransactionModel.fromMap(Map<String, Object?> map) {
    return TransactionModel(
      id: map['id']! as String,
      cardId: map['card_id'] as String?,
      paymentMode: PaymentMode.fromValue(map['payment_mode']! as String),
      amount: (map['amount']! as num).toDouble(),
      discountAmount: (map['discount_amount']! as num).toDouble(),
      cashbackAmount: (map['cashback_amount']! as num).toDouble(),
      finalAmount: (map['final_amount']! as num).toDouble(),
      txnDate: DateTime.parse(map['txn_date']! as String).toUtc(),
      isForSomeoneElse: (map['is_for_someone_else']! as int) == 1,
      personId: map['person_id'] as String?,
      reimbursementStatus: ReimbursementStatus.fromValue(map['reimbursement_status']! as String),
      category: map['category'] as String?,
      notes: map['notes'] as String?,
      createdAt: DateTime.parse(map['created_at']! as String).toUtc(),
      updatedAt: DateTime.parse(map['updated_at']! as String).toUtc(),
    );
  }
}
