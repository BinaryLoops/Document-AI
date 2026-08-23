import 'package:flutter/material.dart';

import '../../models/generated_document_model.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// Issuing Authority — Pending Requests (`GET /generate/requests`), with
/// approve (`POST /generate/approve/{id}`) and reject
/// (`POST /generate/reject/{id}`) actions.
class PendingRequestsScreen extends StatefulWidget {
  const PendingRequestsScreen({super.key});

  @override
  State<PendingRequestsScreen> createState() => _PendingRequestsScreenState();
}

class _PendingRequestsScreenState extends State<PendingRequestsScreen> {
  late Future<List<GeneratedDocumentModel>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<GeneratedDocumentModel>> _load() async {
    final raw = await ApiService.instance.pendingGenerationRequests();
    return raw.map((e) => GeneratedDocumentModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> _refresh() async {
    setState(() => _future = _load());
    await _future;
  }

  Future<void> _approve(GeneratedDocumentModel request) async {
    try {
      await ApiService.instance.approveGeneration(request.requestId);
      if (mounted) showSuccessSnackbar(context, 'Request approved — proceed to sign & issue.');
      await _refresh();
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    }
  }

  Future<void> _reject(GeneratedDocumentModel request) async {
    final reason = await _promptReason(context);
    if (reason == null) return;
    try {
      await ApiService.instance.rejectGeneration(request.requestId, reason: reason);
      if (mounted) showSuccessSnackbar(context, 'Request rejected.');
      await _refresh();
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    }
  }

  Future<String?> _promptReason(BuildContext context) async {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reject Request'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(labelText: 'Reason for rejection'),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, controller.text.trim()), child: const Text('Reject')),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Pending Requests')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<GeneratedDocumentModel>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return ListView(children: [
                EmptyState(
                  icon: Icons.error_outline_rounded,
                  title: 'Could not load requests',
                  subtitle: snapshot.error.toString().replaceFirst('ApiException: ', ''),
                ),
              ]);
            }
            final requests = snapshot.data ?? [];
            if (requests.isEmpty) {
              return ListView(children: const [
                EmptyState(
                  icon: Icons.inbox_outlined,
                  title: 'No pending requests',
                  subtitle: 'Citizen document requests awaiting your approval will appear here.',
                ),
              ]);
            }
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: requests.length,
              itemBuilder: (context, index) {
                final req = requests[index];
                return Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(req.documentType.isEmpty ? 'Document Request' : req.documentType,
                            style: const TextStyle(fontWeight: FontWeight.w700)),
                        if (req.citizenName != null) Text('Applicant: ${req.citizenName}'),
                        Text('Request ID: ${req.requestId}', style: const TextStyle(fontSize: 11.5)),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
                                onPressed: () => _reject(req),
                                icon: const Icon(Icons.close_rounded, size: 18),
                                label: const Text('Reject'),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: FilledButton.icon(
                                onPressed: () => _approve(req),
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
