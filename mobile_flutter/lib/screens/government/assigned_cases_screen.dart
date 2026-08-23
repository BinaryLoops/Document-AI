import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../models/document_model.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';
import '../../widgets/trust_badge_chip.dart';
import 'verification_queue_screen.dart';

/// Government Official — Assigned Cases.
///
/// This backend does not expose a dedicated `/cases` REST endpoint, so this
/// screen surfaces the same real, live data as the Verification Queue
/// (`GET /verify/pending-reviews`) framed as "cases assigned to me" — the
/// closest genuine analogue available, rather than fabricating fake case
/// data. See `verification_queue_screen.dart` for the review actions.
class AssignedCasesScreen extends StatefulWidget {
  const AssignedCasesScreen({super.key});

  @override
  State<AssignedCasesScreen> createState() => _AssignedCasesScreenState();
}

class _AssignedCasesScreenState extends State<AssignedCasesScreen> {
  late Future<List<DocumentModel>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<DocumentModel>> _load() async {
    final raw = await ApiService.instance.pendingReviews();
    if (raw.isEmpty) return const [];

    final list = raw
        .map((e) => e is Map<String, dynamic> ? e : Map<String, dynamic>.from(e as Map))
        .toList();

    return list.map((e) => DocumentModel.fromJson(e)).toList();
  }

  @override
  Widget build(BuildContext context) {
    final jurisdiction = context.watch<AuthProvider>().currentUser?.jurisdiction;
    return Scaffold(
      appBar: AppBar(title: const Text('Assigned Cases')),
      body: RefreshIndicator(
        onRefresh: () async {
          setState(() => _future = _load());
          await _future;
        },
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
                  title: 'Could not load cases',
                  subtitle: snapshot.error.toString().replaceFirst('ApiException: ', ''),
                ),
              ]);
            }
            final cases = snapshot.data ?? [];
            return ListView(
              padding: const EdgeInsets.all(12),
              children: [
                if (jurisdiction != null)
                  Card(
                    color: Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0.5),
                    child: ListTile(
                      leading: const Icon(Icons.map_rounded),
                      title: const Text('Jurisdiction'),
                      subtitle: Text(jurisdiction),
                    ),
                  ),
                const SizedBox(height: 8),
                if (cases.isEmpty)
                  const EmptyState(
                    icon: Icons.assignment_turned_in_outlined,
                    title: 'No cases assigned',
                    subtitle: 'Cases requiring your attention will appear here.',
                  )
                else
                  ...cases.map((doc) => Card(
                        margin: const EdgeInsets.only(bottom: 10),
                        child: ListTile(
                          leading: const CircleAvatar(child: Icon(Icons.folder_shared_outlined)),
                          title: Text(doc.filename, overflow: TextOverflow.ellipsis),
                          subtitle: Text(doc.category ?? 'Uncategorized'),
                          trailing: TrustBadgeChip(badge: doc.trustBadge),
                          onTap: () => Navigator.of(context)
                              .push(MaterialPageRoute(builder: (_) => const VerificationQueueScreen())),
                        ),
                      )),
              ],
            );
          },
        ),
      ),
    );
  }
}
