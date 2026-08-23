import 'package:flutter/material.dart';

import '../../core/constants.dart';
import '../../models/document_model.dart';
import '../../models/verification_model.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';
import '../../widgets/trust_badge_chip.dart';

/// Shows document metadata + extracted fields, and drives the government
/// verification pipeline (Phase 5): upload -> OCR -> classification ->
/// serial/QR/registry checks -> duplicate/fraud score -> trust badge.
class DocumentDetailScreen extends StatefulWidget {
  final String documentId;
  final Map<String, dynamic>? initialData;

  const DocumentDetailScreen({super.key, required this.documentId, this.initialData});

  @override
  State<DocumentDetailScreen> createState() => _DocumentDetailScreenState();
}

class _DocumentDetailScreenState extends State<DocumentDetailScreen> {
  DocumentModel? _document;
  VerificationResult? _verification;
  bool _loading = true;
  bool _verifying = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      Map<String, dynamic> data;
      try {
        data = await ApiService.instance.getDocument(widget.documentId);
      } catch (_) {
        data = widget.initialData ?? {'document_id': widget.documentId};
      }
      _document = DocumentModel.fromJson(data);

      try {
        final history = await ApiService.instance.verificationHistory(widget.documentId);
        if (history.isNotEmpty) {
          _verification = VerificationResult.fromJson(history.last as Map<String, dynamic>);
        }
      } catch (_) {
        // No verification run yet — that's fine.
      }
    } catch (e) {
      _error = e.toString().replaceFirst('ApiException: ', '');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _runVerification() async {
    setState(() => _verifying = true);
    try {
      final result = await ApiService.instance.verifyDocument(documentId: widget.documentId);
      setState(() => _verification = VerificationResult.fromJson(result));
      if (mounted) showSuccessSnackbar(context, 'Verification pipeline completed');
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    } finally {
      if (mounted) setState(() => _verifying = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Document Details')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? EmptyState(icon: Icons.error_outline_rounded, title: 'Something went wrong', subtitle: _error!)
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: Row(
                            children: [
                              CircleAvatar(
                                radius: 26,
                                backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                                child: const Icon(Icons.description_outlined, size: 26),
                              ),
                              const SizedBox(width: 14),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(_document?.filename ?? 'Document',
                                        style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                                    const SizedBox(height: 4),
                                    Text(_document?.category ?? 'Uncategorized',
                                        style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
                                  ],
                                ),
                              ),
                              TrustBadgeChip(
                                badge: _verification?.trustBadge ?? _document?.trustBadge ?? TrustBadge.unknown,
                                large: true,
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SectionHeader(title: 'Government Verification'),
                      Card(
                        child: Padding(
                          padding: const EdgeInsets.all(16),
                          child: _verification == null
                              ? Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    const Text(
                                        'Run the 12-step verification pipeline: OCR quality, classification, '
                                        'serial/QR/registry checks, duplicate detection and fraud scoring.'),
                                    const SizedBox(height: 14),
                                    FilledButton.icon(
                                      onPressed: _verifying ? null : _runVerification,
                                      icon: _verifying
                                          ? const SizedBox(
                                              height: 16,
                                              width: 16,
                                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                                          : const Icon(Icons.verified_rounded),
                                      label: Text(_verifying ? 'Verifying...' : 'Verify Now'),
                                    ),
                                  ],
                                )
                              : Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(
                                      children: [
                                        const Text('Status: ', style: TextStyle(fontWeight: FontWeight.w600)),
                                        Text(_verification!.status),
                                      ],
                                    ),
                                    const SizedBox(height: 6),
                                    Row(
                                      children: [
                                        const Text('Fraud score: ', style: TextStyle(fontWeight: FontWeight.w600)),
                                        Text('${(_verification!.fraudScore * 100).toStringAsFixed(1)}%'),
                                      ],
                                    ),
                                    if (_verification!.steps.isNotEmpty) ...[
                                      const SizedBox(height: 12),
                                      ..._verification!.steps.map((s) => Padding(
                                            padding: const EdgeInsets.symmetric(vertical: 3),
                                            child: Row(
                                              children: [
                                                Icon(
                                                  s.passed ? Icons.check_circle_rounded : Icons.cancel_rounded,
                                                  size: 16,
                                                  color: s.passed ? Colors.green : Colors.red,
                                                ),
                                                const SizedBox(width: 8),
                                                Expanded(child: Text(s.name, style: const TextStyle(fontSize: 13))),
                                              ],
                                            ),
                                          )),
                                    ],
                                    const SizedBox(height: 10),
                                    OutlinedButton.icon(
                                      onPressed: _verifying ? null : _runVerification,
                                      icon: const Icon(Icons.refresh_rounded),
                                      label: const Text('Re-verify'),
                                    ),
                                  ],
                                ),
                        ),
                      ),
                      if (_document != null && _document!.extractedFields.isNotEmpty) ...[
                        const SectionHeader(title: 'Extracted Fields'),
                        ..._document!.extractedFields.map((f) => Card(
                              margin: const EdgeInsets.only(bottom: 8),
                              child: ListTile(
                                dense: true,
                                title: Text(f.field.replaceAll('_', ' ').toUpperCase()),
                                subtitle: Text(f.value ?? '—'),
                                trailing: Text('${(f.confidence * 100).toStringAsFixed(0)}%'),
                              ),
                            )),
                      ],
                    ],
                  ),
                ),
    );
  }
}
