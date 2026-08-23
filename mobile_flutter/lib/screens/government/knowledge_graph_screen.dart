import 'package:flutter/material.dart';

import '../../models/graph_model.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// Government Official — Knowledge Graph explorer (Phase 7).
///
/// A full interactive D3-style force graph is out of scope for a first
/// pass here; instead this gives officers a genuinely useful structured
/// view: aggregate stats + entities grouped by type with their relations,
/// backed by the real `/graph/stats` and `/graph/export` endpoints.
class KnowledgeGraphScreen extends StatefulWidget {
  const KnowledgeGraphScreen({super.key});

  @override
  State<KnowledgeGraphScreen> createState() => _KnowledgeGraphScreenState();
}

class _KnowledgeGraphScreenState extends State<KnowledgeGraphScreen> {
  Map<String, dynamic>? _stats;
  GraphData _graph = GraphData.empty();
  bool _loading = true;
  String? _error;
  String? _selectedType;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final stats = await ApiService.instance.graphStats();
      final export = await ApiService.instance.graphExport();
      setState(() {
        _stats = stats;
        _graph = GraphData.fromJson(export);
      });
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('ApiException: ', ''));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final types = _graph.nodes.map((n) => n.type).toSet().toList()..sort();
    final visibleNodes =
        _selectedType == null ? _graph.nodes : _graph.nodes.where((n) => n.type == _selectedType).toList();

    return Scaffold(
      appBar: AppBar(title: const Text('Knowledge Graph'), actions: [
        IconButton(onPressed: _load, icon: const Icon(Icons.refresh_rounded)),
      ]),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? EmptyState(icon: Icons.error_outline_rounded, title: 'Could not load graph', subtitle: _error!,
                  action: FilledButton(onPressed: _load, child: const Text('Retry')))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      Row(
                        children: [
                          Expanded(child: _statCard(context, 'Nodes', '${_stats?['node_count'] ?? _graph.nodes.length}')),
                          const SizedBox(width: 10),
                          Expanded(child: _statCard(context, 'Edges', '${_stats?['edge_count'] ?? _graph.edges.length}')),
                        ],
                      ),
                      const SectionHeader(title: 'Filter by Entity Type'),
                      Wrap(
                        spacing: 8,
                        children: [
                          ChoiceChip(
                              label: const Text('All'), selected: _selectedType == null, onSelected: (_) => setState(() => _selectedType = null)),
                          ...types.map((t) => ChoiceChip(
                                label: Text(t),
                                selected: _selectedType == t,
                                onSelected: (_) => setState(() => _selectedType = t),
                              )),
                        ],
                      ),
                      const SectionHeader(title: 'Entities'),
                      if (visibleNodes.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 24),
                          child: Text('No entities found. Upload documents to auto-populate the graph.'),
                        ),
                      ...visibleNodes.map((node) {
                        final relations = _graph.edges.where((e) => e.source == node.id || e.target == node.id).toList();
                        return Card(
                          margin: const EdgeInsets.only(bottom: 8),
                          child: ExpansionTile(
                            leading: CircleAvatar(child: Text(node.type.isNotEmpty ? node.type[0] : '?')),
                            title: Text(node.label),
                            subtitle: Text('${node.type} · ${relations.length} relation(s)'),
                            children: relations
                                .map((r) => ListTile(
                                      dense: true,
                                      leading: const Icon(Icons.arrow_right_alt_rounded),
                                      title: Text(r.relation),
                                      subtitle: Text(r.source == node.id ? '→ ${r.target}' : '← ${r.source}'),
                                    ))
                                .toList(),
                          ),
                        );
                      }),
                    ],
                  ),
                ),
    );
  }

  Widget _statCard(BuildContext context, String label, String value) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 18),
        child: Column(
          children: [
            Text(value, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
            Text(label, style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
          ],
        ),
      ),
    );
  }
}
