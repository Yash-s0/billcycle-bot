import 'package:camera/camera.dart';
import 'package:flutter/material.dart';

import '../data/card_scan_service.dart';
import '../domain/card_scan_result.dart';

enum ScannerPhase {
  idle,
  capturing,
  ocr,
  result,
  error,
  closed,
}

class CardScannerScreen extends StatefulWidget {
  const CardScannerScreen({super.key});

  @override
  State<CardScannerScreen> createState() => _CardScannerScreenState();
}

class _CardScannerScreenState extends State<CardScannerScreen> {
  CameraController? _controller;
  final CardScanService _scanService = CardScanService();
  bool _initializing = true;
  ScannerPhase _phase = ScannerPhase.idle;
  String _status = 'Align card in frame';

  @override
  void initState() {
    super.initState();
    _initCamera();
  }

  Future<void> _initCamera() async {
    try {
      final List<CameraDescription> cameras = await availableCameras();
      if (cameras.isEmpty) {
        setState(() {
          _initializing = false;
          _phase = ScannerPhase.error;
          _status = 'No camera found on this device.';
        });
        return;
      }

      final CameraDescription camera = cameras.firstWhere(
        (CameraDescription c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );

      final CameraController controller = CameraController(
        camera,
        ResolutionPreset.high,
        enableAudio: false,
      );
      await controller.initialize();

      if (!mounted) {
        await controller.dispose();
        return;
      }

      setState(() {
        _controller = controller;
        _initializing = false;
        _phase = ScannerPhase.idle;
        _status = 'Align card in frame and tap capture';
      });
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _initializing = false;
        _phase = ScannerPhase.error;
        _status = _mapCameraInitError(e);
      });
    }
  }

  String _mapCameraInitError(Object error) {
    final String msg = error.toString().toLowerCase();
    if (msg.contains('cameraaccessdenied') || msg.contains('permission')) {
      return 'Camera permission denied. Enable camera permission and retry.';
    }
    if (msg.contains('camera') && msg.contains('in use')) {
      return 'Camera is currently in use by another app.';
    }
    if (msg.contains('not available')) {
      return 'Camera is not available right now.';
    }
    return 'Failed to open camera.';
  }

  String _mapCaptureOrOcrError(Object error) {
    final String msg = error.toString().toLowerCase();
    if (msg.contains('capturealreadyactive') || msg.contains('capture is already pending')) {
      return 'Capture is busy. Try again in a moment.';
    }
    if (msg.contains('camera') && msg.contains('closed')) {
      return 'Camera session reset. Reopen scanner and try again.';
    }
    if (msg.contains('permission')) {
      return 'Camera permission issue. Check app permissions.';
    }
    if (msg.contains('mlkit') || msg.contains('text recognition') || msg.contains('ocr')) {
      return 'Could not read card text. Adjust lighting and keep card flat, then retry.';
    }
    return 'Capture failed. Please try again.';
  }

  Future<void> _captureAndDetect() async {
    if (_controller == null || !_controller!.value.isInitialized) {
      return;
    }
    if (_phase == ScannerPhase.capturing || _phase == ScannerPhase.ocr || _phase == ScannerPhase.closed) {
      return;
    }

    try {
      setState(() {
        _phase = ScannerPhase.capturing;
        _status = 'Capturing image...';
      });

      final XFile image = await _controller!.takePicture();

      if (!mounted) {
        return;
      }
      setState(() {
        _phase = ScannerPhase.ocr;
        _status = 'Reading card details...';
      });

      final CardScanParseResult parsed = await _scanService.parseImagePath(image.path);

      if (!mounted) {
        return;
      }

      setState(() {
        _phase = ScannerPhase.result;
      });

      await _showConfirmSheet(parsed);

      if (!mounted) {
        return;
      }
      if (_phase != ScannerPhase.closed) {
        setState(() {
          _phase = ScannerPhase.idle;
          _status = 'Align card in frame and tap capture';
        });
      }
    } catch (e) {
      if (!mounted) {
        return;
      }
      setState(() {
        _phase = ScannerPhase.idle;
        _status = _mapCaptureOrOcrError(e);
      });
    }
  }

  Future<void> _showConfirmSheet(CardScanParseResult parsed) async {
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
            : 'We could not confidently detect details. Retake with better light or use gallery.';

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

    if (!mounted) {
      return;
    }

    if (apply == true) {
      final String bank = bankController.text.trim();
      final String last4 = last4Controller.text.trim();
      _phase = ScannerPhase.closed;
      Navigator.of(context).pop(
        CardScanConfirmedResult(
          bankName: bank,
          last4: last4,
          rawOcrText: parsed.ocrSnippet,
        ),
      );
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    _scanService.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final bool busy = _phase == ScannerPhase.capturing || _phase == ScannerPhase.ocr;

    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        title: const Text('Scan card'),
        backgroundColor: Colors.black,
      ),
      body: _initializing
          ? const Center(child: CircularProgressIndicator())
          : (_controller == null || !_controller!.value.isInitialized)
              ? Center(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text(
                      _status,
                      style: const TextStyle(color: Colors.white),
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              : Stack(
                  children: <Widget>[
                    Positioned.fill(child: CameraPreview(_controller!)),
                    Center(
                      child: Container(
                        width: 320,
                        height: 210,
                        decoration: BoxDecoration(
                          border: Border.all(color: Colors.cyanAccent, width: 2),
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                    ),
                    const Positioned(
                      left: 16,
                      right: 16,
                      bottom: 130,
                      child: Text(
                        'Center align the card inside the box.',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Colors.white,
                          fontWeight: FontWeight.w600,
                          shadows: <Shadow>[Shadow(blurRadius: 6, color: Colors.black)],
                        ),
                      ),
                    ),
                    Positioned(
                      left: 16,
                      right: 16,
                      bottom: 92,
                      child: Text(
                        _status,
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: Colors.white70),
                      ),
                    ),
                    Positioned(
                      left: 0,
                      right: 0,
                      bottom: 24,
                      child: Center(
                        child: FilledButton.icon(
                          onPressed: busy ? null : _captureAndDetect,
                          icon: busy
                              ? const SizedBox(
                                  width: 16,
                                  height: 16,
                                  child: CircularProgressIndicator(strokeWidth: 2),
                                )
                              : const Icon(Icons.camera_alt_outlined),
                          label: Text(busy ? 'Processing...' : 'Capture now'),
                        ),
                      ),
                    ),
                  ],
                ),
    );
  }
}
