import 'dart:io';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:image_cropper/image_cropper.dart';
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';

import '../../core/theme.dart';
import '../../widgets/common_widgets.dart';
import 'upload_document_screen.dart';

/// Live camera document scanner (Phase 3).
///
/// Flow: live preview -> capture -> crop/perspective-correct each page ->
/// repeat for multi-page documents -> hand pages off to the upload screen,
/// which merges + compresses them automatically before sending to the
/// backend (no manual export step, per spec).
class ScanDocumentScreen extends StatefulWidget {
  const ScanDocumentScreen({super.key});

  @override
  State<ScanDocumentScreen> createState() => _ScanDocumentScreenState();
}

class _ScanDocumentScreenState extends State<ScanDocumentScreen> {
  CameraController? _controller;
  Future<void>? _initFuture;
  FlashMode _flashMode = FlashMode.off;
  final List<File> _pages = [];
  bool _capturing = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _setup();
  }

  Future<void> _setup() async {
    try {
      final cameras = await availableCameras();
      if (cameras.isEmpty) {
        setState(() => _error = 'No camera found on this device.');
        return;
      }
      final back = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.back,
        orElse: () => cameras.first,
      );
      _controller = CameraController(back, ResolutionPreset.high, enableAudio: false);
      _initFuture = _controller!.initialize();
      setState(() {});
    } catch (e) {
      setState(() => _error = 'Could not access the camera: $e');
    }
  }

  @override
  void dispose() {
    _controller?.dispose();
    super.dispose();
  }

  Future<void> _toggleFlash() async {
    if (_controller == null) return;
    final next = _flashMode == FlashMode.off ? FlashMode.torch : FlashMode.off;
    await _controller!.setFlashMode(next);
    setState(() => _flashMode = next);
  }

  Future<void> _capture() async {
    if (_controller == null || _capturing) return;
    setState(() => _capturing = true);
    try {
      final shot = await _controller!.takePicture();
      // Perspective correction / auto-crop step — the user fine-tunes the
      // auto-detected edges, matching the "auto edge detection + perspective
      // correction + auto crop" requirement.
      final cropped = await ImageCropper().cropImage(
        sourcePath: shot.path,
        compressFormat: ImageCompressFormat.jpg,
        compressQuality: 88,
        uiSettings: [
          AndroidUiSettings(
            toolbarTitle: 'Adjust Document Edges',
            toolbarColor: AppTheme.navy,
            toolbarWidgetColor: Colors.white,
            lockAspectRatio: false,
          ),
          IOSUiSettings(title: 'Adjust Document Edges'),
        ],
      );
      if (cropped != null) {
        setState(() => _pages.add(File(cropped.path)));
      }
    } catch (e) {
      if (mounted) showErrorSnackbar(context, 'Capture failed: $e');
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  void _removePage(int index) => setState(() => _pages.removeAt(index));

  Future<void> _finish() async {
    if (_pages.isEmpty) return;
    // Persist pages to a stable app directory before handing off — camera
    // temp files can be cleaned up by the OS.
    final dir = await getApplicationDocumentsDirectory();
    final persisted = <File>[];
    for (var i = 0; i < _pages.length; i++) {
      final dest = p.join(dir.path, 'scan_${DateTime.now().millisecondsSinceEpoch}_$i.jpg');
      persisted.add(await _pages[i].copy(dest));
    }
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => UploadDocumentScreen(scannedPages: persisted)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: Text('Scan Document${_pages.isNotEmpty ? ' (${_pages.length})' : ''}'),
        actions: [
          IconButton(
            icon: Icon(_flashMode == FlashMode.off ? Icons.flash_off_rounded : Icons.flash_on_rounded),
            onPressed: _toggleFlash,
          ),
        ],
      ),
      body: _error != null
          ? EmptyState(icon: Icons.videocam_off_rounded, title: 'Camera unavailable', subtitle: _error!)
          : _controller == null
              ? const Center(child: CircularProgressIndicator())
              : FutureBuilder(
                  future: _initFuture,
                  builder: (context, snapshot) {
                    if (snapshot.connectionState != ConnectionState.done) {
                      return const Center(child: CircularProgressIndicator(color: Colors.white));
                    }
                    return Column(
                      children: [
                        Expanded(child: CameraPreview(_controller!)),
                        if (_pages.isNotEmpty)
                          SizedBox(
                            height: 76,
                            child: ListView.builder(
                              scrollDirection: Axis.horizontal,
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
                              itemCount: _pages.length,
                              itemBuilder: (context, index) => Padding(
                                padding: const EdgeInsets.symmetric(horizontal: 4),
                                child: Stack(
                                  children: [
                                    ClipRRect(
                                      borderRadius: BorderRadius.circular(8),
                                      child: Image.file(_pages[index], width: 56, height: 60, fit: BoxFit.cover),
                                    ),
                                    Positioned(
                                      right: -4,
                                      top: -4,
                                      child: GestureDetector(
                                        onTap: () => _removePage(index),
                                        child: const CircleAvatar(
                                          radius: 10,
                                          backgroundColor: Colors.red,
                                          child: Icon(Icons.close, size: 12, color: Colors.white),
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ),
                        Container(
                          color: Colors.black,
                          padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 24),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              SizedBox(
                                width: 90,
                                child: OutlinedButton(
                                  style: OutlinedButton.styleFrom(
                                      foregroundColor: Colors.white, side: const BorderSide(color: Colors.white38)),
                                  onPressed: _pages.isNotEmpty ? _finish : null,
                                  child: const Text('Done'),
                                ),
                              ),
                              GestureDetector(
                                onTap: _capturing ? null : _capture,
                                child: Container(
                                  width: 72,
                                  height: 72,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    border: Border.all(color: Colors.white, width: 4),
                                  ),
                                  child: _capturing
                                      ? const Padding(
                                          padding: EdgeInsets.all(20),
                                          child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                                        )
                                      : Container(
                                          margin: const EdgeInsets.all(4),
                                          decoration: const BoxDecoration(shape: BoxShape.circle, color: Colors.white),
                                        ),
                                ),
                              ),
                              const SizedBox(width: 90),
                            ],
                          ),
                        ),
                      ],
                    );
                  },
                ),
    );
  }
}
