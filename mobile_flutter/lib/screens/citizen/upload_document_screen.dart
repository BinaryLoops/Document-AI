import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:pdf/widgets.dart' as pw;

import '../../services/api_service.dart';
import '../../services/storage_service.dart';
import '../../widgets/common_widgets.dart';
import 'document_detail_screen.dart';

/// Upload flow (Phase 3 continuation + Phase 4/5/6 integration):
/// takes either freshly scanned pages or a manually picked file, silently
/// compresses/merges them, uploads to `/documents/upload`, then shows the
/// OCR and trained document-classification result returned by the backend.
class UploadDocumentScreen extends StatefulWidget {
  final List<File>? scannedPages;
  const UploadDocumentScreen({super.key, this.scannedPages});

  @override
  State<UploadDocumentScreen> createState() => _UploadDocumentScreenState();
}

class _UploadDocumentScreenState extends State<UploadDocumentScreen> {
  File? _pickedFile;
  bool _uploading = false;
  bool _finalizing = false;
  double _progressStage = 0;
  String _stageLabel = '';
  Map<String, dynamic>? _result;
  String? _error;
  String _category = 'Application';

  static const _categories = [
    'Application',
    'Identity Proof',
    'Address Proof',
    'Certificate',
    'Affidavit',
    'Other',
  ];

  @override
  void initState() {
    super.initState();
    if (widget.scannedPages != null && widget.scannedPages!.isNotEmpty) {
      _processScannedPages(widget.scannedPages!);
    }
  }

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'png', 'jpg', 'jpeg', 'docx', 'txt'],
    );
    if (result != null && result.files.single.path != null) {
      setState(() {
        _pickedFile = File(result.files.single.path!);
        _result = null;
        _error = null;
      });
    }
  }

  /// Merges multi-page scans into a single compressed PDF automatically —
  /// no manual export step for the user.
  Future<void> _processScannedPages(List<File> pages) async {
    setState(() {
      _uploading = true;
      _stageLabel = 'Compressing & enhancing scan...';
    });
    try {
      if (pages.length == 1) {
        final compressed = await _compress(pages.first);
        setState(() => _pickedFile = compressed);
      } else {
        final doc = pw.Document();
        for (final page in pages) {
          final compressed = await _compress(page);
          final bytes = await compressed.readAsBytes();
          final image = pw.MemoryImage(bytes);
          doc.addPage(
            pw.Page(build: (context) => pw.Center(child: pw.Image(image))),
          );
        }
        final dir = await getApplicationDocumentsDirectory();
        final outPath = p.join(
          dir.path,
          'scan_${DateTime.now().millisecondsSinceEpoch}.pdf',
        );
        final outFile = File(outPath);
        await outFile.writeAsBytes(await doc.save());
        setState(() => _pickedFile = outFile);
      }
      setState(() => _uploading = false);
      await _upload();
    } catch (e) {
      setState(() {
        _uploading = false;
        _error = 'Failed to process scanned pages: $e';
      });
    }
  }

  Future<File> _compress(File original) async {
    final bytes = await original.readAsBytes();
    final decoded = img.decodeImage(bytes);
    if (decoded == null) return original;
    final resized = decoded.width > 1600
        ? img.copyResize(decoded, width: 1600)
        : decoded;
    final jpg = img.encodeJpg(resized, quality: 82);
    final out = File('${original.path}_c.jpg');
    await out.writeAsBytes(jpg);
    return out;
  }

  Future<void> _upload() async {
    if (_pickedFile == null) return;
    setState(() {
      _uploading = true;
      _stageLabel = 'Uploading to secure server...';
      _error = null;
      _progressStage = 0.3;
    });
    try {
      setState(() {
        _stageLabel = 'Running OCR + document classification...';
        _progressStage = 0.7;
      });
      final result = await ApiService.instance.processDocument(_pickedFile!);
      final suggested = _categoryForDocumentType(
        result['document_type']?.toString(),
      );
      // Documents come back as "pending_review" first — they're analyzed
      // (OCR + classification + field extraction) but held temporarily on
      // the server, not yet saved permanently. Only a confirmed document is
      // persisted locally; this lets the citizen catch a wrong file or a
      // bad scan before it becomes part of their record.
      if (result['status'] != 'pending_review') {
        await StorageService.instance.saveLocalDocument({
          ...result,
          'filename': p.basename(_pickedFile!.path),
          'uploaded_at': DateTime.now().toIso8601String(),
          if (suggested != null) 'category': suggested,
        });
      }
      setState(() {
        _result = result;
        if (suggested != null) _category = suggested;
        _progressStage = 1;
      });
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('ApiException: ', ''));
    } finally {
      setState(() => _uploading = false);
    }
  }

  /// Keeps the reviewed document: finalizes it on the server (indexing +
  /// knowledge graph) and only then saves it into the citizen's local
  /// document list.
  Future<void> _confirm() async {
    final documentId = (_result?['document_id'] ?? _result?['id'])?.toString();
    if (documentId == null) return;
    setState(() {
      _finalizing = true;
      _error = null;
    });
    try {
      final result = await ApiService.instance.confirmDocument(documentId);
      final suggested = _categoryForDocumentType(
        result['document_type']?.toString(),
      );
      await StorageService.instance.saveLocalDocument({
        ...result,
        'filename': _pickedFile != null
            ? p.basename(_pickedFile!.path)
            : result['filename'],
        'uploaded_at': DateTime.now().toIso8601String(),
        if (suggested != null) 'category': suggested,
      });
      setState(() {
        _result = result;
        if (suggested != null) _category = suggested;
      });
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('ApiException: ', ''));
    } finally {
      setState(() => _finalizing = false);
    }
  }

  /// Discards the reviewed document (wrong file, poor scan, etc.) and
  /// resets the screen so the citizen can pick/scan another one.
  Future<void> _discard() async {
    final documentId = (_result?['document_id'] ?? _result?['id'])?.toString();
    setState(() {
      _finalizing = true;
      _error = null;
    });
    try {
      if (documentId != null) {
        await ApiService.instance.discardDocument(documentId);
      }
    } catch (_) {
      // Best-effort — even if the discard call fails (e.g. already expired
      // server-side), let the citizen move on and try another upload.
    } finally {
      setState(() {
        _finalizing = false;
        _result = null;
        _pickedFile = null;
        _progressStage = 0;
      });
    }
  }

  String? _categoryForDocumentType(String? documentType) {
    if (documentType == null) return null;
    final normalized = documentType.toLowerCase();
    if (normalized.contains('identity') || normalized.contains('passport')) {
      return 'Identity Proof';
    }
    if (normalized.contains('address')) {
      return 'Address Proof';
    }
    if (normalized.contains('certificate')) {
      return 'Certificate';
    }
    if (normalized.contains('affidavit')) {
      return 'Affidavit';
    }
    if (normalized.contains('application')) {
      return 'Application';
    }
    return 'Other';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Upload Document')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (_pickedFile == null) _buildPicker(context),
              if (_pickedFile != null && _result == null && !_uploading)
                _buildReadyToUpload(context),
              if (_uploading) _buildProgress(context),
              if (_error != null) _buildError(context),
              if (_result != null) _buildResult(context),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPicker(BuildContext context) {
    return DottedBox(
      onTap: _pickFile,
      child: Column(
        children: [
          Icon(
            Icons.upload_file_rounded,
            size: 56,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 12),
          const Text(
            'Tap to select a document',
            style: TextStyle(fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 4),
          Text(
            'PDF, PNG, JPG, DOCX, TXT',
            style: TextStyle(
              fontSize: 12,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildReadyToUpload(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Card(
          child: ListTile(
            leading: const Icon(Icons.insert_drive_file_rounded),
            title: Text(
              p.basename(_pickedFile!.path),
              overflow: TextOverflow.ellipsis,
            ),
            trailing: IconButton(
              icon: const Icon(Icons.close),
              onPressed: () => setState(() => _pickedFile = null),
            ),
          ),
        ),
        const SizedBox(height: 12),
        const Text(
          'Document Category',
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 8),
        if (_result == null)
          Text(
            'Choose a category, or let document classification suggest one after processing.',
            style: TextStyle(
              fontSize: 12,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        Wrap(
          spacing: 8,
          children: _categories
              .map(
                (c) => ChoiceChip(
                  label: Text(c),
                  selected: _category == c,
                  onSelected: (_) => setState(() => _category = c),
                ),
              )
              .toList(),
        ),
        const SizedBox(height: 20),
        FilledButton.icon(
          onPressed: _upload,
          icon: const Icon(Icons.cloud_upload_rounded),
          label: const Text('Upload & Process'),
        ),
      ],
    );
  }

  Widget _buildProgress(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            LinearProgressIndicator(
              value: _progressStage == 0 ? null : _progressStage,
            ),
            const SizedBox(height: 14),
            Text(
              _stageLabel,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildError(BuildContext context) {
    return Card(
      color: Theme.of(context).colorScheme.errorContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(
              Icons.error_outline_rounded,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(width: 10),
            Expanded(child: Text(_error!)),
          ],
        ),
      ),
    );
  }

  Widget _buildResult(BuildContext context) {
    final r = _result!;
    if (r['status'] == 'queued') {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Row(
            children: [
              const Icon(Icons.cloud_off_rounded, color: Colors.orange),
              const SizedBox(width: 12),
              Expanded(
                child: Text(r['message']?.toString() ?? 'Upload queued.'),
              ),
            ],
          ),
        ),
      );
    }
    final docType = r['document_type']?.toString() ?? 'Document';
    final confidence =
        (r['classification_confidence'] as num?)?.toDouble() ?? 0.0;
    final fields = (r['extracted_fields'] as List?) ?? [];
    final documentId = (r['document_id'] ?? r['id'])?.toString();
    final isPendingReview = r['status'] == 'pending_review';

    final fieldsWithValues = fields
        .where((f) => f is Map && (f['value'] as Object?) != null)
        .toList();
    final displayFields = fieldsWithValues.isNotEmpty ? fieldsWithValues : fields;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Card(
          color: (isPendingReview ? Colors.orange : Colors.green)
              .withValues(alpha: 0.08),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Icon(
                  isPendingReview
                      ? Icons.rate_review_rounded
                      : Icons.check_circle_rounded,
                  color: isPendingReview ? Colors.orange : Colors.green,
                  size: 28,
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        isPendingReview
                            ? 'Review Before Saving'
                            : 'Saved Successfully',
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                      Text(
                        'Classified as "$docType" (${(confidence * 100).toStringAsFixed(0)}% confidence)',
                        style: const TextStyle(fontSize: 12.5),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
        if (isPendingReview) ...[
          const SizedBox(height: 10),
          Text(
            'Check the details detected below. Confirm to save this document, '
            'or discard it to upload a different file or a clearer scan.',
            style: TextStyle(
              fontSize: 12.5,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ],
        if (displayFields.isNotEmpty) ...[
          SectionHeader(title: 'Extracted Fields'),
          ...displayFields
              .take(8)
              .map(
                (f) => Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    dense: true,
                    title: Text(
                      f['field']
                              ?.toString()
                              .replaceAll('_', ' ')
                              .toUpperCase() ??
                          '',
                    ),
                    subtitle: Text(f['value']?.toString() ?? 'Not detected'),
                    trailing: Text(
                      '${(((f['confidence'] as num?) ?? 0) * 100).toStringAsFixed(0)}%',
                    ),
                  ),
                ),
              ),
        ],
        const SizedBox(height: 16),
        if (isPendingReview)
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _finalizing ? null : _discard,
                  icon: const Icon(Icons.replay_rounded),
                  label: const Text('Discard & Retry'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton.icon(
                  onPressed: _finalizing ? null : _confirm,
                  icon: _finalizing
                      ? const SizedBox(
                          height: 16,
                          width: 16,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Icon(Icons.check_rounded),
                  label: const Text('Confirm & Save'),
                ),
              ),
            ],
          )
        else
          Row(
            children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () =>
                      Navigator.of(context).popUntil((r) => r.isFirst),
                  child: const Text('Done'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton(
                  onPressed: documentId == null
                      ? null
                      : () => Navigator.of(context).pushReplacement(
                          MaterialPageRoute(
                            builder: (_) => DocumentDetailScreen(
                              documentId: documentId,
                              initialData: r,
                            ),
                          ),
                        ),
                  child: const Text('View & Verify'),
                ),
              ),
            ],
          ),
      ],
    );
  }
}

class DottedBox extends StatelessWidget {
  final Widget child;
  final VoidCallback onTap;
  const DottedBox({super.key, required this.child, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(vertical: 48),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: Theme.of(context).colorScheme.outline,
            width: 1.4,
          ),
        ),
        child: child,
      ),
    );
  }
}
