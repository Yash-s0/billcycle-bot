import 'package:billcycle_mobile/features/cards/data/card_scan_parser.dart';
import 'package:billcycle_mobile/features/cards/domain/card_scan_result.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final CardScanParser parser = CardScanParser();

  test('parses bank and last4 from typical card text', () {
    final result = parser.parse('HDFC Bank\nCredit Card\n4586 1024 5555 1234');

    expect(result.suggestedBank, 'HDFC');
    expect(result.suggestedLast4, '1234');
    expect(result.confidence, CardScanConfidence.high);
  });

  test('handles compact card number text', () {
    final result = parser.parse('ICICI Bank card no 4111111111119876');

    expect(result.suggestedBank, 'ICICI');
    expect(result.suggestedLast4, '9876');
    expect(result.confidence, CardScanConfidence.high);
  });

  test('extracts masked last4 patterns', () {
    final result = parser.parse('AXIS bank credit card xx1234 successful');

    expect(result.suggestedBank, 'Axis');
    expect(result.suggestedLast4, '1234');
    expect(result.confidence, CardScanConfidence.medium);
  });

  test('returns low confidence when no bank/number detected', () {
    final result = parser.parse('hello world no card data');

    expect(result.suggestedBank, isNull);
    expect(result.suggestedLast4, isNull);
    expect(result.confidence, CardScanConfidence.low);
  });
}
