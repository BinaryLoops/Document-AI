import 'package:flutter/material.dart';

import '../../core/constants.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// Issuing Authority — direct document issuance (Phase 9: "Only Issuing
/// Authority may generate documents"). Same field-schema-driven form pattern
/// as the citizen request flow (`generate_document_form_screen.dart`), but
/// invoked directly by the authorized signer, backed by
/// `GET /generate/template/{doc_type}` + `POST /generate/{doc_type}`.
class IssueDocumentScreen extends StatefulWidget {
  final GovDocumentType? initialType;
  const IssueDocumentScreen({super.key, this.initialType});

  @override
  State<IssueDocumentScreen> createState() => _IssueDocumentScreenState();
}

class _IssueDocumentScreenState extends State<IssueDocumentScreen> {
  final _formKey = GlobalKey<FormState>();
  final Map<String, TextEditingController> _controllers = {};
  GovDocumentType? _selectedType;
  List<Map<String, dynamic>> _fields = [];
  bool _loadingTemplate = false;
  bool _submitting = false;
  Map<String, dynamic>? _issued;

  static const _fallbackFields = [
    {'name': 'full_name', 'label': 'Applicant Full Name', 'required': true},
    {'name': 'date_of_birth', 'label': 'Date of Birth (YYYY-MM-DD)', 'required': true},
    {'name': 'address', 'label': 'Address', 'required': true},
    {'name': 'aadhaar_number', 'label': 'Aadhaar Number', 'required': true},
  ];

  @override
  void initState() {
    super.initState();
    if (widget.initialType != null) {
      _selectedType = widget.initialType;
      _loadTemplate();
    }
  }

  Future<void> _loadTemplate() async {
    if (_selectedType == null) return;
    setState(() => _loadingTemplate = true);
    try {
      final template = await ApiService.instance.generationTemplate(_selectedType!.apiPath);
      final fields = (template['fields'] as List?)?.cast<Map<String, dynamic>>();
      _fields = (fields != null && fields.isNotEmpty) ? fields : _fallbackFields.cast<Map<String, dynamic>>();
    } catch (_) {
      _fields = _fallbackFields.cast<Map<String, dynamic>>();
    }
    _controllers.clear();
    for (final f in _fields) {
      _controllers[f['name'].toString()] = TextEditingController();
    }
    if (mounted) setState(() => _loadingTemplate = false);
  }

  Future<void> _submit() async {
    if (_selectedType == null || !_formKey.currentState!.validate()) return;
    setState(() => _submitting = true);
    try {
      final data = {for (final e in _controllers.entries) e.key: e.value.text.trim()};
      final result = await ApiService.instance.generateDocument(docType: _selectedType!.apiPath, fields: data);
      setState(() => _issued = result);
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Issue Document')),
      body: _issued != null
          ? _buildIssued(context)
          : SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Form(
                key: _formKey,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Document Type', style: TextStyle(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 10),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: GovDocumentType.values
                          .map((t) => ChoiceChip(
                                label: Text(t.displayName),
                                selected: _selectedType == t,
                                onSelected: (_) {
                                  setState(() => _selectedType = t);
                                  _loadTemplate();
                                },
                              ))
                          .toList(),
                    ),
                    const SizedBox(height: 20),
                    if (_loadingTemplate) const Center(child: CircularProgressIndicator()),
                    if (_selectedType != null && !_loadingTemplate) ...[
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
                      FilledButton.icon(
                        onPressed: _submitting ? null : _submit,
                        icon: _submitting
                            ? const SizedBox(
                                height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                            : const Icon(Icons.verified_rounded),
                        label: Text(_submitting ? 'Signing & Issuing...' : 'Digitally Sign & Issue'),
                      ),
                    ],
                  ],
                ),
              ),
            ),
    );
  }

  Widget _buildIssued(BuildContext context) {
    final docNumber = (_issued!['document_number'] ?? _issued!['request_id'])?.toString() ?? '—';
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.verified_rounded, color: Colors.green, size: 64),
          const SizedBox(height: 16),
          const Text('Document Issued & Signed', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text('Document Number: $docNumber', style: const TextStyle(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          const Text(
            'The document has been digitally signed and a verification QR code embedded. '
            'The citizen has been notified and can track delivery.',
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          FilledButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Done')),
        ],
      ),
    );
  }
}
