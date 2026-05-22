import '../domain/card_scan_result.dart';

class CardScanParser {
  static const Map<String, String> _knownBanks = <String, String>{
    'hdfc': 'HDFC',
    'icici': 'ICICI',
    'axis': 'Axis',
    'sbi': 'SBI',
    'kotak': 'Kotak',
    'yes bank': 'YES BANK',
    'indusind': 'IndusInd',
    'amex': 'AMEX',
    'american express': 'American Express',
    'citibank': 'Citibank',
    'citi': 'Citi',
    'au bank': 'AU BANK',
    'idfc': 'IDFC',
    'rbl': 'RBL',
    'federal bank': 'Federal Bank',
    'standard chartered': 'Standard Chartered',
    'hsbc': 'HSBC',
  };

  CardScanParseResult parse(String text) {
    final String normalized = text.toLowerCase();
    final String compact = text.replaceAll(RegExp(r'[^0-9\s\-*xX]'), ' ');

    final String? number = _extractCardNumberCandidate(compact);
    final String? last4FromNumber = number == null || number.length < 4 ? null : number.substring(number.length - 4);
    final String? last4Masked = _extractMaskedLast4(normalized);
    final String? last4 = last4FromNumber ?? last4Masked;
    final String? bank = _extractBank(normalized);

    final CardScanConfidence confidence = _confidence(bank: bank, number: number, last4: last4);

    return CardScanParseResult(
      suggestedBank: bank,
      suggestedLast4: last4,
      rawCardNumber: number,
      ocrSnippet: _snippet(text),
      confidence: confidence,
    );
  }

  CardScanConfidence _confidence({String? bank, String? number, String? last4}) {
    if (bank != null && number != null) {
      return CardScanConfidence.high;
    }
    if (bank != null && last4 != null) {
      return CardScanConfidence.medium;
    }
    if (number != null || last4 != null) {
      return CardScanConfidence.medium;
    }
    return CardScanConfidence.low;
  }

  String _snippet(String text) {
    final String t = text.replaceAll(RegExp(r'\s+'), ' ').trim();
    if (t.length <= 140) {
      return t;
    }
    return '${t.substring(0, 140)}...';
  }

  String? _extractCardNumberCandidate(String compact) {
    final RegExp grouped = RegExp(r'(?<!\d)(?:\d{4}[ -]?){3}\d{4,7}(?!\d)');
    final Match? groupedMatch = grouped.firstMatch(compact);
    if (groupedMatch != null) {
      final String cleaned = groupedMatch.group(0)!.replaceAll(RegExp(r'[^0-9]'), '');
      if (cleaned.length >= 12 && cleaned.length <= 19) {
        return cleaned;
      }
    }

    final RegExp contiguous = RegExp(r'(?<!\d)\d{12,19}(?!\d)');
    final Match? contiguousMatch = contiguous.firstMatch(compact);
    if (contiguousMatch != null) {
      return contiguousMatch.group(0);
    }

    final String digitsOnly = compact.replaceAll(RegExp(r'[^0-9]'), ' ');
    final List<String> parts = digitsOnly.split(RegExp(r'\s+')).where((String s) => s.isNotEmpty).toList(growable: false);
    for (final String p in parts) {
      if (p.length >= 12 && p.length <= 19) {
        return p;
      }
    }

    return null;
  }

  String? _extractMaskedLast4(String normalized) {
    final RegExp masked = RegExp(r'(?:\*{2,}|x{2,})\s*(\d{4})', caseSensitive: false);
    final Match? match = masked.firstMatch(normalized);
    return match?.group(1);
  }

  String? _extractBank(String normalized) {
    for (final MapEntry<String, String> bank in _knownBanks.entries) {
      if (normalized.contains(bank.key)) {
        return bank.value;
      }
    }
    return null;
  }
}
