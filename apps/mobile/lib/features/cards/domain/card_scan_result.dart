enum CardScanConfidence {
  low,
  medium,
  high,
}

class CardScanParseResult {
  const CardScanParseResult({
    required this.suggestedBank,
    required this.suggestedLast4,
    required this.rawCardNumber,
    required this.ocrSnippet,
    required this.confidence,
  });

  final String? suggestedBank;
  final String? suggestedLast4;
  final String? rawCardNumber;
  final String ocrSnippet;
  final CardScanConfidence confidence;

  bool get hasAnySuggestion => suggestedBank != null || suggestedLast4 != null;
}

class CardScanConfirmedResult {
  const CardScanConfirmedResult({
    required this.bankName,
    required this.last4,
    required this.rawOcrText,
  });

  final String bankName;
  final String last4;
  final String rawOcrText;
}
