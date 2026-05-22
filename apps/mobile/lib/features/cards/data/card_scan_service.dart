import 'package:google_mlkit_text_recognition/google_mlkit_text_recognition.dart';
import 'package:image_picker/image_picker.dart';

import '../domain/card_scan_result.dart';
import 'card_scan_parser.dart';

class CardScanService {
  CardScanService({ImagePicker? picker, TextRecognizer? recognizer})
      : _picker = picker ?? ImagePicker(),
        _recognizer = recognizer ?? TextRecognizer(script: TextRecognitionScript.latin);

  final ImagePicker _picker;
  final TextRecognizer _recognizer;
  final CardScanParser _parser = CardScanParser();

  Future<CardScanParseResult?> scanFromGallery() async {
    final XFile? image = await _picker.pickImage(
      source: ImageSource.gallery,
      imageQuality: 85,
    );

    if (image == null) {
      return null;
    }

    return parseImagePath(image.path);
  }

  Future<CardScanParseResult> parseImagePath(String path) async {
    final InputImage inputImage = InputImage.fromFilePath(path);
    final RecognizedText recognized = await _recognizer.processImage(inputImage);
    return _parser.parse(recognized.text);
  }

  Future<void> dispose() async {
    await _recognizer.close();
  }
}
