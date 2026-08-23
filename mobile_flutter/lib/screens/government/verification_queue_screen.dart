import 'package:flutter/material.dart';

import '../../models/document_model.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';
import '../../widgets/trust_badge_chip.dart';

/// Government Official — Verification Queue (Phase 2/5). Lists documents
/// awaiting manual review (`GET /verify/pending-reviews`) and lets the
/// officer approve/reject via `POST /verify/manual-review`.
///
/// NOTE: this backend has no separate `/cases` endpoint, so "Assigned Cases"
/// on the dashboard reuses this same pending-reviews queue as its data
/// source — it is the closest real analogue available.
class VerificationQueueScreen extends StatefulWidget {
  const VerificationQueueScreen({super.key});

  @override
  State<VerificationQueueScreen> createState() => _VerificationQueueScreenState();
}

class _VerificationQueueScreenState extends State<VerificationQueueScreen> {
  late Future<List<DocumentModel>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<DocumentModel>> _load() async {
    final raw = await ApiService.instance.pendingReviews();
    return raw.map((e) => DocumentModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> _refresh() async {
    final next = _load();
    setState(() => _future = next);
    await next;
  }

  Future<void> _decide(DocumentModel doc, String decision) async {
    try {
      await ApiService.instance.submitManualReview(documentId: doc.id, decision: decision);
      if (mounted) showSuccessSnackbar(context, 'Review submitted: $decision');
      await _refresh();
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Verification Queue')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<DocumentModel>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return ListView(children: [
                EmptyState(
                  icon: Icons.error_outline_rounded,
                  title: 'Could not load queue',
                  subtitle: snapshot.error.toString().replaceFirst('ApiException: ', ''),
                  action: FilledButton(onPressed: _refresh, child: const Text('Retry')),
                ),
              ]);
            }
            final docs = snapshot.data ?? [];
            if (docs.isEmpty) {
              return ListView(children: const [
                EmptyState(
                  icon: Icons.fact_check_outlined,
                  title: 'Queue is empty',
                  subtitle: 'No documents are currently awaiting manual review.',
                ),
              ]);
            }
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: docs.length,
              itemBuilder: (context, index) {
                final doc = docs[index];
                return Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Flexible(
                              child: Text(doc.filename,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(fontWeight: FontWeight.w700)),
                            ),
                            const SizedBox(width: 8),
                            TrustBadgeChip(badge: doc.trustBadge),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Text(doc.category ?? 'Uncategorized',
                            style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12.5)),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
                                onPressed: () => _decide(doc, 'rejected'),
                                icon: const Icon(Icons.close_rounded, size: 18),
                                label: const Text('Reject'),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: FilledButton.icon(
                                onPressed: () => _decide(doc, 'approved'),
                                icon: const Icon(Icons.check_rounded, size: 18),
                                label: const Text('Approve'),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
