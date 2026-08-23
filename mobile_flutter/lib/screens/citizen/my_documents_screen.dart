import 'package:flutter/material.dart';

import '../../models/document_model.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';
import '../../widgets/trust_badge_chip.dart';
import 'document_detail_screen.dart';

class MyDocumentsScreen extends StatefulWidget {
  const MyDocumentsScreen({super.key});

  @override
  State<MyDocumentsScreen> createState() => _MyDocumentsScreenState();
}

class _MyDocumentsScreenState extends State<MyDocumentsScreen> {
  late Future<List<DocumentModel>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<DocumentModel>> _load() async {
    final raw = await ApiService.instance.listDocuments();
    return raw.map((e) => DocumentModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> _refresh() async {
    setState(() => _future = _load());
    await _future;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Documents')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<DocumentModel>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return ListView(
                children: [
                  EmptyState(
                    icon: Icons.error_outline_rounded,
                    title: 'Could not load documents',
                    subtitle: snapshot.error.toString().replaceFirst('ApiException: ', ''),
                    action: FilledButton(onPressed: _refresh, child: const Text('Retry')),
                  ),
                ],
              );
            }
            final docs = snapshot.data ?? [];
            if (docs.isEmpty) {
              return ListView(
                children: const [
                  EmptyState(
                    icon: Icons.folder_off_outlined,
                    title: 'No documents yet',
                    subtitle: 'Scan or upload your first document to get started.',
                  ),
                ],
              );
            }
            return ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: docs.length,
              itemBuilder: (context, index) {
                final doc = docs[index];
                return Card(
                  margin: const EdgeInsets.only(bottom: 10),
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                    leading: CircleAvatar(
                      backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                      child: const Icon(Icons.description_outlined),
                    ),
                    title: Text(doc.filename, maxLines: 1, overflow: TextOverflow.ellipsis),
                    subtitle: Text(doc.category ?? 'Uncategorized'),
                    trailing: TrustBadgeChip(badge: doc.trustBadge),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) => DocumentDetailScreen(documentId: doc.id))),
                  ),
                );
              },
            );
          },
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.of(context).pushNamed('/citizen/upload'),
        icon: const Icon(Icons.add_rounded),
        label: const Text('Add'),
      ),
    );
  }
}
