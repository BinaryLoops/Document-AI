import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// Government Official — Upload Case Files (`POST /documents/upload`),
/// attaching a supporting document to a citizen's case by owner id.
class UploadCaseFileScreen extends StatefulWidget {
  const UploadCaseFileScreen({super.key});

  @override
  State<UploadCaseFileScreen> createState() => _UploadCaseFileScreenState();
}

class _UploadCaseFileScreenState extends State<UploadCaseFileScreen> {
  final _ownerController = TextEditingController();
  File? _file;
  bool _uploading = false;
  Map<String, dynamic>? _result;

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'png', 'jpg', 'jpeg', 'docx', 'txt'],
    );
    if (result != null && result.files.single.path != null) {
      setState(() => _file = File(result.files.single.path!));
    }
  }

  Future<void> _upload() async {
    if (_file == null || _ownerController.text.trim().isEmpty) return;
    setState(() => _uploading = true);
    try {
      final result = await ApiService.instance.uploadDocument(
        file: _file!,
        category: 'Case File',
        ownerId: _ownerController.text.trim(),
      );
      setState(() => _result = result);
      if (mounted) showSuccessSnackbar(context, 'Case file uploaded successfully');
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    } finally {
      if (mounted) setState(() => _uploading = false);
    }
  }

  @override
  void dispose() {
    _ownerController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Upload Case File')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _ownerController,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(
                labelText: 'Citizen ID / Aadhaar / Case Owner',
                prefixIcon: Icon(Icons.person_outline_rounded),
              ),
            ),
            const SizedBox(height: 16),
            InkWell(
              onTap: _pickFile,
              borderRadius: BorderRadius.circular(16),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 36),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Theme.of(context).colorScheme.outline),
                ),
                child: Column(
                  children: [
                    Icon(_file == null ? Icons.upload_file_rounded : Icons.insert_drive_file_rounded,
                        size: 42, color: Theme.of(context).colorScheme.primary),
                    const SizedBox(height: 8),
                    Text(_file == null ? 'Tap to select a case file' : _file!.path.split(Platform.pathSeparator).last),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: (_file != null && _ownerController.text.trim().isNotEmpty && !_uploading) ? _upload : null,
              icon: _uploading
                  ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.cloud_upload_rounded),
              label: Text(_uploading ? 'Uploading...' : 'Upload Case File'),
            ),
            if (_result != null) ...[
              const SectionHeader(title: 'Result'),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                      'Classified as "${_result!['document_type'] ?? 'Document'}" and attached to the case file.'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
