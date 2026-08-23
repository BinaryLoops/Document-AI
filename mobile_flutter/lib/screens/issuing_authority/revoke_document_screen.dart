import 'package:flutter/material.dart';

import '../../core/constants.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';
import 'issue_document_screen.dart';

/// Issuing Authority — Revoke / Reissue a document.
///
/// Lookup uses the public QR-verify endpoint (`GET /generate/verify/{number}`)
/// to fetch document details, then revokes via
/// `POST /generate/revoke/{document_id}`. "Reissue" is modelled as revoke +
/// deep-link into a fresh Issue Document form for the same document type,
/// since there is no dedicated reissue endpoint.
class RevokeDocumentScreen extends StatefulWidget {
  const RevokeDocumentScreen({super.key});

  @override
  State<RevokeDocumentScreen> createState() => _RevokeDocumentScreenState();
}

class _RevokeDocumentScreenState extends State<RevokeDocumentScreen> {
  final _numberController = TextEditingController();
  final _reasonController = TextEditingController();
  Map<String, dynamic>? _document;
  bool _loading = false;
  bool _revoking = false;
  String? _error;

  Future<void> _lookup() async {
    final number = _numberController.text.trim();
    if (number.isEmpty) return;
    setState(() {
      _loading = true;
      _error = null;
      _document = null;
    });
    try {
      final result = await ApiService.instance.verifyByDocumentNumber(number);
      setState(() => _document = result);
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('ApiException: ', ''));
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _revoke() async {
    final documentId = (_document?['document_id'] ?? _document?['id'])?.toString();
    if (documentId == null) return;
    setState(() => _revoking = true);
    try {
      await ApiService.instance.revokeDocument(documentId, reason: _reasonController.text.trim());
      if (mounted) showSuccessSnackbar(context, 'Document revoked successfully.');
      setState(() => _document = null);
      _numberController.clear();
      _reasonController.clear();
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    } finally {
      if (mounted) setState(() => _revoking = false);
    }
  }

  void _reissue() {
    GovDocumentType? type;
    final docType = _document?['document_type']?.toString();
    for (final t in GovDocumentType.values) {
      if (t.apiPath == docType || t.displayName == docType) type = t;
    }
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => IssueDocumentScreen(initialType: type)));
  }

  @override
  void dispose() {
    _numberController.dispose();
    _reasonController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Revoke / Reissue')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _numberController,
                    decoration: const InputDecoration(labelText: 'Document Number', prefixIcon: Icon(Icons.qr_code_rounded)),
                    onSubmitted: (_) => _lookup(),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(onPressed: _loading ? null : _lookup, child: const Text('Lookup')),
              ],
            ),
            const SizedBox(height: 16),
            if (_loading) const Center(child: CircularProgressIndicator()),
            if (_error != null)
              EmptyState(icon: Icons.search_off_rounded, title: 'Document not found', subtitle: _error!),
            if (_document != null) ...[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(_document!['document_type']?.toString() ?? 'Document',
                          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
                      const SizedBox(height: 4),
                      Text('Holder: ${_document!['citizen_name'] ?? _document!['holder_name'] ?? '—'}'),
                      Text('Status: ${_document!['status'] ?? '—'}'),
                      Text('Issued: ${_document!['issued_at'] ?? '—'}'),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _reasonController,
                decoration: const InputDecoration(labelText: 'Reason for revocation'),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: _reissue,
                      icon: const Icon(Icons.autorenew_rounded),
                      label: const Text('Reissue'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton.icon(
                      style: FilledButton.styleFrom(backgroundColor: Colors.red),
                      onPressed: _revoking ? null : _revoke,
                      icon: _revoking
                          ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : const Icon(Icons.block_rounded),
                      label: Text(_revoking ? 'Revoking...' : 'Revoke'),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
