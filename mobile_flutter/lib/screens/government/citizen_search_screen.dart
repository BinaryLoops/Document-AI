import 'package:flutter/material.dart';

import '../../models/document_model.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';
import '../../widgets/trust_badge_chip.dart';

/// Government Official — Citizen Search (`GET /documents/search?q=`).
/// Searches across document metadata/content — the closest real analogue to
/// a citizen registry search this backend exposes.
class CitizenSearchScreen extends StatefulWidget {
  const CitizenSearchScreen({super.key});

  @override
  State<CitizenSearchScreen> createState() => _CitizenSearchScreenState();
}

class _CitizenSearchScreenState extends State<CitizenSearchScreen> {
  final _queryController = TextEditingController();
  List<DocumentModel>? _results;
  bool _loading = false;
  String? _error;

  Future<void> _search() async {
    final query = _queryController.text.trim();
    if (query.isEmpty) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final raw = await ApiService.instance.searchDocuments(query);
      setState(() => _results = raw.map((e) => DocumentModel.fromJson(e as Map<String, dynamic>)).toList());
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('ApiException: ', ''));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Citizen Search')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _queryController,
                    decoration: const InputDecoration(
                      hintText: 'Search by name, Aadhaar, or document content',
                      prefixIcon: Icon(Icons.search_rounded),
                    ),
                    onSubmitted: (_) => _search(),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(onPressed: _loading ? null : _search, child: const Text('Search')),
              ],
            ),
            const SizedBox(height: 16),
            if (_loading) const Center(child: CircularProgressIndicator()),
            if (_error != null)
              EmptyState(icon: Icons.error_outline_rounded, title: 'Search failed', subtitle: _error!),
            if (_results != null)
              Expanded(
                child: _results!.isEmpty
                    ? const EmptyState(
                        icon: Icons.person_search_rounded,
                        title: 'No matches found',
                        subtitle: 'Try a different name, Aadhaar number, or keyword.',
                      )
                    : ListView.builder(
                        itemCount: _results!.length,
                        itemBuilder: (context, index) {
                          final doc = _results![index];
                          return Card(
                            margin: const EdgeInsets.only(bottom: 8),
                            child: ListTile(
                              leading: const CircleAvatar(child: Icon(Icons.description_outlined)),
                              title: Text(doc.filename, overflow: TextOverflow.ellipsis),
                              subtitle: Text(doc.category ?? 'Uncategorized'),
                              trailing: TrustBadgeChip(badge: doc.trustBadge),
                            ),
                          );
                        },
                      ),
              ),
          ],
        ),
      ),
    );
  }
}
