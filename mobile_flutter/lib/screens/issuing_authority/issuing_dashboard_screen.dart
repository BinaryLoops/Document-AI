import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/generated_document_model.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';
import 'issue_document_screen.dart';
import 'pending_requests_screen.dart';
import 'revoke_document_screen.dart';

class IssuingDashboardScreen extends StatefulWidget {
  const IssuingDashboardScreen({super.key});

  @override
  State<IssuingDashboardScreen> createState() => _IssuingDashboardScreenState();
}

class _IssuingDashboardScreenState extends State<IssuingDashboardScreen> {
  late Future<List<GeneratedDocumentModel>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<GeneratedDocumentModel>> _load() async {
    final raw = await ApiService.instance.allGeneratedDocuments();
    return raw.map((e) => GeneratedDocumentModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    return Scaffold(
      appBar: AppBar(title: const Text('Issuing Authority')),
      body: RefreshIndicator(
        onRefresh: () async {
          setState(() => _future = _load());
          await _future;
        },
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              color: const Color(0xFFC62828),
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 26,
                      backgroundColor: Colors.white.withValues(alpha: 0.2),
                      child: const Icon(Icons.verified_user_rounded, color: Colors.white, size: 28),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(user?.name ?? 'Officer',
                              style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w700)),
                          Text(user?.departmentCode ?? 'Issuing Authority',
                              style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 12)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Card(
                color: Colors.red.withValues(alpha: 0.08),
                child: const Padding(
                  padding: EdgeInsets.all(12),
                  child: Row(
                    children: [
                      Icon(Icons.gavel_rounded, size: 18, color: Colors.red),
                      SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'Only Issuing Authorities may issue, digitally sign, revoke, or reissue government documents.',
                          style: TextStyle(fontSize: 11.5),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SectionHeader(title: 'Actions'),
            GridView.count(
              crossAxisCount: 3,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 10,
              crossAxisSpacing: 10,
              childAspectRatio: 0.95,
              children: [
                QuickActionCard(
                  icon: Icons.inbox_rounded,
                  label: 'Pending\nRequests',
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PendingRequestsScreen())),
                ),
                QuickActionCard(
                  icon: Icons.edit_document,
                  label: 'Issue\nDocument',
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const IssueDocumentScreen())),
                ),
                QuickActionCard(
                  icon: Icons.block_rounded,
                  label: 'Revoke /\nReissue',
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const RevokeDocumentScreen())),
                ),
              ],
            ),
            const SectionHeader(title: 'Recently Issued'),
            FutureBuilder<List<GeneratedDocumentModel>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 30),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                if (snapshot.hasError) {
                  return EmptyState(
                    icon: Icons.error_outline_rounded,
                    title: 'Could not load issued documents',
                    subtitle: snapshot.error.toString().replaceFirst('ApiException: ', ''),
                  );
                }
                final docs = snapshot.data ?? [];
                if (docs.isEmpty) {
                  return const EmptyState(
                    icon: Icons.description_outlined,
                    title: 'No documents issued yet',
                    subtitle: 'Documents you issue will be listed here.',
                  );
                }
                return Column(
                  children: docs.take(10).map((d) => Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: ListTile(
                          leading: const Icon(Icons.description_rounded),
                          title: Text(d.documentType),
                          subtitle: Text(d.citizenName ?? d.documentNumber ?? d.requestId),
                          trailing: Chip(label: Text(d.status)),
                        ),
                      )).toList(),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
