import 'package:flutter/material.dart';

import '../../core/constants.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// Dynamic request form for a government document, built from the backend's
/// field schema (`GET /generate/template/{doc_type}`), falling back to a
/// sensible generic set of fields if the template can't be fetched.
class GenerateDocumentFormScreen extends StatefulWidget {
  final GovDocumentType docType;
  const GenerateDocumentFormScreen({super.key, required this.docType});

  @override
  State<GenerateDocumentFormScreen> createState() => _GenerateDocumentFormScreenState();
}

class _GenerateDocumentFormScreenState extends State<GenerateDocumentFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final Map<String, TextEditingController> _controllers = {};
  List<Map<String, dynamic>> _fields = [];
  bool _loadingTemplate = true;
  bool _submitting = false;
  Map<String, dynamic>? _submitted;

  static const _fallbackFields = [
    {'name': 'full_name', 'label': 'Full Name', 'required': true},
    {'name': 'date_of_birth', 'label': 'Date of Birth (YYYY-MM-DD)', 'required': true},
    {'name': 'address', 'label': 'Address', 'required': true},
    {'name': 'aadhaar_number', 'label': 'Aadhaar Number', 'required': true},
    {'name': 'reason', 'label': 'Reason / Purpose', 'required': false},
  ];

  @override
  void initState() {
    super.initState();
    _loadTemplate();
  }

  Future<void> _loadTemplate() async {
    try {
      final template = await ApiService.instance.generationTemplate(widget.docType.apiPath);
      final fields = (template['fields'] as List?)?.cast<Map<String, dynamic>>();
      _fields = (fields != null && fields.isNotEmpty) ? fields : _fallbackFields.cast<Map<String, dynamic>>();
    } catch (_) {
      _fields = _fallbackFields.cast<Map<String, dynamic>>();
    }
    for (final f in _fields) {
      _controllers[f['name'].toString()] = TextEditingController();
    }
    if (mounted) setState(() => _loadingTemplate = false);
  }

  @override
  void dispose() {
    for (final c in _controllers.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _submitting = true);
    try {
      final data = {for (final e in _controllers.entries) e.key: e.value.text.trim()};
      final result = await ApiService.instance.requestDocument(docType: widget.docType.apiPath, fields: data);
      setState(() => _submitted = result);
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Request: ${widget.docType.displayName}')),
      body: _loadingTemplate
          ? const Center(child: CircularProgressIndicator())
          : _submitted != null
              ? _buildSubmitted(context)
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(20),
                  child: Form(
                    key: _formKey,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Fill in the required details below. Your request will be reviewed by the '
                          'relevant Issuing Authority before the document is signed and released.',
                          style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 13),
                        ),
                        const SizedBox(height: 20),
                        ..._fields.map((f) {
                          final name = f['name'].toString();
                          final required = f['required'] == true;
                          return Padding(
                            padding: const EdgeInsets.only(bottom: 14),
                            child: TextFormField(
                              controller: _controllers[name],
                              decoration: InputDecoration(labelText: f['label']?.toString() ?? name),
                              validator: (v) =>
                                  required && (v == null || v.trim().isEmpty) ? 'This field is required' : null,
                            ),
                          );
                        }),
                        const SizedBox(height: 10),
                        FilledButton(
                          onPressed: _submitting ? null : _submit,
                          child: _submitting
                              ? const SizedBox(
                                  height: 20,
                                  width: 20,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : const Text('Submit Request'),
                        ),
                      ],
                    ),
                  ),
                ),
    );
  }

  Widget _buildSubmitted(BuildContext context) {
    final requestId = (_submitted!['request_id'] ?? _submitted!['id'])?.toString() ?? '—';
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.check_circle_rounded, color: Colors.green, size: 64),
          const SizedBox(height: 16),
          const Text('Request Submitted', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text('Reference ID: $requestId', style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          Text(
            'You will be notified once the Issuing Authority approves and digitally signs your document. '
            'Track its progress from the Delivery Tracking screen.',
            textAlign: TextAlign.center,
            style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant),
          ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: () => Navigator.of(context).popUntil((r) => r.isFirst),
            child: const Text('Back to Dashboard'),
          ),
        ],
      ),
    );
  }
}
