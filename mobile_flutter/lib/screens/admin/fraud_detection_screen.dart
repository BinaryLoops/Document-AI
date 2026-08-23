import 'package:flutter/material.dart';

import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// System Admin — Fraud Detection: suspicious tightly-connected entity
/// clusters (`GET /graph/fraud-clusters`) and fuzzy-matched duplicate
/// citizen identities (`GET /graph/duplicates`).
class FraudDetectionScreen extends StatefulWidget {
  const FraudDetectionScreen({super.key});

  @override
  State<FraudDetectionScreen> createState() => _FraudDetectionScreenState();
}

class _FraudDetectionScreenState extends State<FraudDetectionScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  late Future<List<dynamic>> _clustersFuture;
  late Future<List<dynamic>> _duplicatesFuture;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _clustersFuture = ApiService.instance.fraudClusters();
    _duplicatesFuture = ApiService.instance.duplicateCitizens();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Fraud Detection'),
        bottom: TabBar(controller: _tabController, tabs: const [
          Tab(text: 'Fraud Clusters'),
          Tab(text: 'Duplicate Identities'),
        ]),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          _buildList(
            future: _clustersFuture,
            emptyTitle: 'No fraud clusters detected',
            emptySubtitle: 'Suspicious tightly-connected entity clusters will appear here.',
            itemBuilder: (item) {
              final risk = (item['risk_score'] as num?)?.toDouble() ?? 0.0;
              return Card(
                margin: const EdgeInsets.only(bottom: 10),
                child: ListTile(
                  leading: CircleAvatar(
                    backgroundColor: risk > 0.7 ? Colors.red.shade100 : Colors.orange.shade100,
                    child: Icon(Icons.report_problem_rounded, color: risk > 0.7 ? Colors.red : Colors.orange),
                  ),
                  title: Text(item['label']?.toString() ?? item['cluster_id']?.toString() ?? 'Cluster'),
                  subtitle: Text('${(item['entities'] as List?)?.length ?? item['size'] ?? '?'} linked entities'),
                  trailing: Text('${(risk * 100).toStringAsFixed(0)}% risk', style: const TextStyle(fontWeight: FontWeight.bold)),
                ),
              );
            },
          ),
          _buildList(
            future: _duplicatesFuture,
            emptyTitle: 'No duplicates found',
            emptySubtitle: 'Fuzzy-matched potential duplicate citizen identities will appear here.',
            itemBuilder: (item) => Card(
              margin: const EdgeInsets.only(bottom: 10),
              child: ListTile(
                leading: const CircleAvatar(child: Icon(Icons.people_alt_rounded)),
                title: Text('${item['name_a'] ?? item['citizen_a'] ?? '?'}  ↔  ${item['name_b'] ?? item['citizen_b'] ?? '?'}'),
                subtitle: Text('Similarity: ${((item['similarity'] as num?)?.toDouble() ?? 0) * 100}%'.replaceAll('.0%', '%')),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildList({
    required Future<List<dynamic>> future,
    required String emptyTitle,
    required String emptySubtitle,
    required Widget Function(Map<String, dynamic>) itemBuilder,
  }) {
    return FutureBuilder<List<dynamic>>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return EmptyState(
            icon: Icons.error_outline_rounded,
            title: 'Could not load data',
            subtitle: snapshot.error.toString().replaceFirst('ApiException: ', ''),
          );
        }
        final items = snapshot.data ?? [];
        if (items.isEmpty) {
          return EmptyState(icon: Icons.shield_moon_outlined, title: emptyTitle, subtitle: emptySubtitle);
        }
        return ListView(
          padding: const EdgeInsets.all(12),
          children: items.map((raw) => itemBuilder(raw as Map<String, dynamic>)).toList(),
        );
      },
    );
  }
}
