import 'package:flutter/material.dart';

import '../../models/document_model.dart';
import '../../models/generated_document_model.dart';
import '../../services/api_service.dart';
import '../../services/storage_service.dart';
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
  late Future<List<GeneratedDocumentModel>> _requestsFuture;

  @override
  void initState() {
    super.initState();
    _future = _load();
    _requestsFuture = _loadRequests();
  }

  Future<List<DocumentModel>> _load() async {
    final local = await StorageService.instance.getLocalDocuments();
    try {
      final raw = await ApiService.instance.listDocuments();
      final remote = raw
          .map((e) => DocumentModel.fromJson(e as Map<String, dynamic>))
          .toList();
      final remoteIds = remote.map((doc) => doc.id).toSet();
      final cached = local
          .where(
            (item) => !remoteIds.contains(item['document_id'] ?? item['id']),
          )
          .map(DocumentModel.fromJson);
      return [...cached, ...remote];
    } catch (_) {
      return local.map(DocumentModel.fromJson).toList();
    }
  }

  Future<List<GeneratedDocumentModel>> _loadRequests() async {
    try {
      final raw = await ApiService.instance.pendingGenerationRequests();
      return raw
          .map(
            (e) => GeneratedDocumentModel.fromJson(e as Map<String, dynamic>),
          )
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> _refresh() async {
    setState(() => _future = _load());
    setState(() => _requestsFuture = _loadRequests());
    await _future;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('My Documents')),
      body: DefaultTabController(
        length: 2,
        child: Column(
          children: [
            const TabBar(
              tabs: [
                Tab(text: 'Uploaded'),
                Tab(text: 'Requested'),
              ],
            ),
            Expanded(
              child: TabBarView(
                children: [
                  RefreshIndicator(
                    onRefresh: _refresh,
                    child: FutureBuilder<List<DocumentModel>>(
                      future: _future,
                      builder: (context, snapshot) {
                        if (snapshot.connectionState ==
                            ConnectionState.waiting) {
                          return const Center(
                            child: CircularProgressIndicator(),
                          );
                        }
                        if (snapshot.hasError) {
                          return ListView(
                            children: [
                              EmptyState(
                                icon: Icons.error_outline_rounded,
                                title: 'Could not load documents',
                                subtitle: snapshot.error
                                    .toString()
                                    .replaceFirst('ApiException: ', ''),
                                action: FilledButton(
                                  onPressed: _refresh,
                                  child: const Text('Retry'),
                                ),
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
                                contentPadding: const EdgeInsets.symmetric(
                                  horizontal: 14,
                                  vertical: 6,
                                ),
                                leading: CircleAvatar(
                                  backgroundColor: Theme.of(context)
                                      .colorScheme
                                      .primaryContainer,
                                  child: const Icon(Icons.description_outlined),
                                ),
                                title: Text(
                                  doc.filename,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                                subtitle: Text(doc.category ?? 'Uncategorized'),
                                trailing: TrustBadgeChip(badge: doc.trustBadge),
                                onTap: () => Navigator.of(context).push(
                                  MaterialPageRoute(
                                    builder: (_) => DocumentDetailScreen(
                                      documentId: doc.id,
                                      initialData: doc.toJson(),
                                    ),
                                  ),
                                ),
                              ),
                            );
                          },
                        );
                      },
                    ),
                  ),
                  _buildRequests(),
                ],
              ),
            ),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => Navigator.of(context).pushNamed('/citizen/upload'),
        icon: const Icon(Icons.add_rounded),
        label: const Text('Add'),
      ),
    );
  }

  Widget _buildRequests() {
    return FutureBuilder<List<GeneratedDocumentModel>>(
      future: _requestsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        final requests = snapshot.data ?? [];
        if (requests.isEmpty) {
          return const EmptyState(
            icon: Icons.assignment_outlined,
            title: 'No document requests',
            subtitle: 'Requested documents will appear here.',
          );
        }
        return ListView.builder(
          padding: const EdgeInsets.all(12),
          itemCount: requests.length,
          itemBuilder: (context, index) {
            final request = requests[index];
            return Card(
              margin: const EdgeInsets.only(bottom: 10),
              child: ListTile(
                leading: const Icon(Icons.assignment_outlined),
                title: Text(request.documentType),
                subtitle: Text('Request ${request.requestId}'),
                trailing: Text(request.status.toUpperCase()),
              ),
            );
          },
        );
      },
    );
  }
}
