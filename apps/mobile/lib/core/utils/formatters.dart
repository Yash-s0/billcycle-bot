import 'package:intl/intl.dart';

String formatCurrency(num amount) => '₹${NumberFormat('#,##0.00').format(amount)}';

String formatDate(DateTime date) => DateFormat('yyyy-MM-dd').format(date.toLocal());

String formatDateShort(DateTime date) => DateFormat('dd MMM').format(date.toLocal());
