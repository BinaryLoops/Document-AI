import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../core/constants.dart';
import '../../core/theme.dart';
import '../../models/document_model.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// Government Official — Reports (Phase 5/7 rollup).
///
/// There is no dedicated `/reports` endpoint, so this screen computes real
/// aggregates client-side from the live pending-reviews and graph-stats
/// endpoints (trust badge distribution, queue size, graph density) and
/// renders them as charts using `fl_chart`.
class ReportsScreen extends StatefulWidget {
  const ReportsScreen({super.key});

  @override
  State<ReportsScreen> createState() => _ReportsScreenState();
}

class _ReportsScreenState extends State<ReportsScreen> {
  bool _loading = true;
  String? _error;
  Map<TrustBadge, int> _badgeCounts = {};
  Map<String, dynamic> _graphStats = {};
  int _queueSize = 0;

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
      final rawDocs = await ApiService.instance.pendingReviews();
      final docs = rawDocs.map((e) => DocumentModel.fromJson(e as Map<String, dynamic>)).toList();
      final counts = <TrustBadge, int>{for (final b in TrustBadge.values) b: 0};
      for (final d in docs) {
        counts[d.trustBadge] = (counts[d.trustBadge] ?? 0) + 1;
      }
      final stats = await ApiService.instance.graphStats();
      setState(() {
        _badgeCounts = counts;
        _queueSize = docs.length;
        _graphStats = stats;
      });
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('ApiException: ', ''));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Reports')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? EmptyState(icon: Icons.error_outline_rounded, title: 'Could not load reports', subtitle: _error!,
                  action: FilledButton(onPressed: _load, child: const Text('Retry')))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      const SectionHeader(title: 'Verification Queue — Trust Badge Distribution'),
                      SizedBox(
                        height: 200,
                        child: _queueSize == 0
                            ? const Center(child: Text('No data yet'))
                            : PieChart(
                                PieChartData(
                                  sections: _badgeCounts.entries
                                      .where((e) => e.value > 0)
                                      .map((e) => PieChartSectionData(
                                            value: e.value.toDouble(),
                                            title: '${e.value}',
                                            color: _colorFor(e.key),
                                            radius: 60,
                                          ))
                                      .toList(),
                                ),
                              ),
                      ),
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 12,
                        alignment: WrapAlignment.center,
                        children: _badgeCounts.entries
                            .map((e) => Chip(
                                  avatar: CircleAvatar(backgroundColor: _colorFor(e.key)),
                                  label: Text('${e.key.label}: ${e.value}'),
                                ))
                            .toList(),
                      ),
                      const SectionHeader(title: 'Knowledge Graph Overview'),
                      Row(
                        children: [
                          Expanded(child: _statCard('Nodes', '${_graphStats['node_count'] ?? 0}')),
                          const SizedBox(width: 10),
                          Expanded(child: _statCard('Edges', '${_graphStats['edge_count'] ?? 0}')),
                        ],
                      ),
                    ],
                  ),
                ),
    );
  }

  Color _colorFor(TrustBadge badge) {
    switch (badge) {
      case TrustBadge.green:
        return AppTheme.emerald;
      case TrustBadge.yellow:
        return AppTheme.amber;
      case TrustBadge.red:
        return AppTheme.crimson;
      case TrustBadge.unknown:
        return Colors.grey;
    }
  }

  Widget _statCard(String label, String value) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 18),
        child: Column(
          children: [
            Text(value, style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold)),
            Text(label),
          ],
        ),
      ),
    );
  }
}
