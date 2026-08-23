import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// System Admin — System Analytics, aggregating `/security/events`,
/// `/security/anomalies` and `/graph/stats` into a single overview.
class AnalyticsScreen extends StatefulWidget {
  const AnalyticsScreen({super.key});

  @override
  State<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends State<AnalyticsScreen> {
  bool _loading = true;
  String? _error;
  List<dynamic> _events = [];
  List<dynamic> _anomalies = [];
  Map<String, dynamic> _graphStats = {};

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
      final events = await ApiService.instance.securityEvents();
      final anomalies = await ApiService.instance.anomalies();
      final stats = await ApiService.instance.graphStats();
      setState(() {
        _events = events;
        _anomalies = anomalies;
        _graphStats = stats;
      });
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('ApiException: ', ''));
    } finally {
      setState(() => _loading = false);
    }
  }

  Map<String, int> get _eventTypeCounts {
    final counts = <String, int>{};
    for (final raw in _events) {
      final e = raw as Map<String, dynamic>;
      final type = (e['type'] ?? e['event_type'] ?? 'unknown').toString();
      counts[type] = (counts[type] ?? 0) + 1;
    }
    return counts;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('System Analytics')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? EmptyState(icon: Icons.error_outline_rounded, title: 'Could not load analytics', subtitle: _error!,
                  action: FilledButton(onPressed: _load, child: const Text('Retry')))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      Row(
                        children: [
                          Expanded(child: _statCard(context, 'Security Events', '${_events.length}', Icons.shield_outlined)),
                          const SizedBox(width: 10),
                          Expanded(child: _statCard(context, 'Anomalies', '${_anomalies.length}', Icons.warning_amber_rounded)),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(child: _statCard(context, 'Graph Nodes', '${_graphStats['node_count'] ?? 0}', Icons.hub_outlined)),
                          const SizedBox(width: 10),
                          Expanded(child: _statCard(context, 'Graph Edges', '${_graphStats['edge_count'] ?? 0}', Icons.share_outlined)),
                        ],
                      ),
                      const SectionHeader(title: 'Security Events by Type'),
                      SizedBox(
                        height: 220,
                        child: _eventTypeCounts.isEmpty
                            ? const Center(child: Text('No security events recorded'))
                            : BarChart(
                                BarChartData(
                                  barGroups: _eventTypeCounts.entries
                                      .toList()
                                      .asMap()
                                      .entries
                                      .map((e) => BarChartGroupData(x: e.key, barRods: [
                                            BarChartRodData(
                                                toY: e.value.value.toDouble(),
                                                color: Theme.of(context).colorScheme.primary,
                                                width: 22)
                                          ]))
                                      .toList(),
                                  titlesData: FlTitlesData(
                                    bottomTitles: AxisTitles(
                                      sideTitles: SideTitles(
                                        showTitles: true,
                                        getTitlesWidget: (value, meta) {
                                          final keys = _eventTypeCounts.keys.toList();
                                          final i = value.toInt();
                                          if (i < 0 || i >= keys.length) return const SizedBox.shrink();
                                          return Padding(
                                            padding: const EdgeInsets.only(top: 6),
                                            child: Text(keys[i], style: const TextStyle(fontSize: 9)),
                                          );
                                        },
                                      ),
                                    ),
                                    leftTitles: const AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 28)),
                                    topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                                    rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
                                  ),
                                ),
                              ),
                      ),
                    ],
                  ),
                ),
    );
  }

  Widget _statCard(BuildContext context, String label, String value, IconData icon) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 10),
        child: Column(
          children: [
            Icon(icon, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 6),
            Text(value, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
            Text(label, style: TextStyle(fontSize: 11, color: Theme.of(context).colorScheme.onSurfaceVariant)),
          ],
        ),
      ),
    );
  }
}
