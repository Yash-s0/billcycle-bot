import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class MoneyText extends StatelessWidget {
  const MoneyText(
    this.amount, {
    super.key,
    this.style,
    this.prefix = '₹',
  });

  final num amount;
  final TextStyle? style;
  final String prefix;

  @override
  Widget build(BuildContext context) {
    final String text = '$prefix${NumberFormat('#,##0.00').format(amount)}';
    return Text(text, style: style);
  }
}
