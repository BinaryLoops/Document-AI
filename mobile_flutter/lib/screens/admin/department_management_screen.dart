import 'package:flutter/material.dart';

import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// System Admin — Department Management.
///
/// This backend exposes no CRUD endpoints for departments, and per the
/// product spec "Admin cannot edit issued documents. Only supervise." — so
/// this screen is intentionally **read-only oversight**, combining
/// `/verify/departments` (verification modules) and `/graph/departments`
/// (officers/documents/cases per department) rather than a fabricated
/// create/edit UI with no backing API.
class DepartmentManagementScreen extends StatefulWidget {
  const DepartmentManagementScreen({super.key});

  @override
  State<DepartmentManagementScreen> createState() => _DepartmentManagementScreenState();
}

class _DepartmentManagementScreenState extends State<DepartmentManagementScreen> {
  bool _loading = true;
  String? _error;
  List<dynamic> _verificationDepartments = [];
  Map<String, dynamic> _graphDepartments = {};

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
      final verifyDepts = await ApiService.instance.verificationDepartments();
      Map<String, dynamic> graphDepts = {};
      try {
        graphDepts = await ApiService.instance.graphDepartments();
      } catch (_) {
        // Optional enrichment — fine if unavailable.
      }
      setState(() {
        _verificationDepartments = verifyDepts;
        _graphDepartments = graphDepts;
      });
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('ApiException: ', ''));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final departmentList = (_graphDepartments['departments'] as List?) ?? [];
    return Scaffold(
      appBar: AppBar(title: const Text('Department Management')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? EmptyState(icon: Icons.error_outline_rounded, title: 'Could not load departments', subtitle: _error!,
                  action: FilledButton(onPressed: _load, child: const Text('Retry')))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      Card(
                        color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
                        child: const Padding(
                          padding: EdgeInsets.all(14),
                          child: Row(
                            children: [
                              Icon(Icons.info_outline_rounded, size: 20),
                              SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  'Read-only oversight view. Admins supervise departments but cannot edit issued '
                                  'documents or department records directly.',
                                  style: TextStyle(fontSize: 12.5),
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SectionHeader(title: 'Verification Modules'),
                      if (_verificationDepartments.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 12),
                          child: Text('No verification department modules registered.'),
                        )
                      else
                        ..._verificationDepartments.map((raw) {
                          final d = raw as Map<String, dynamic>;
                          return Card(
                            margin: const EdgeInsets.only(bottom: 8),
                            child: ListTile(
                              leading: const Icon(Icons.apartment_rounded),
                              title: Text(d['name']?.toString() ?? d['department']?.toString() ?? 'Department'),
                              subtitle: Text(d['description']?.toString() ?? ''),
                            ),
                          );
                        }),
                      if (departmentList.isNotEmpty) ...[
                        const SectionHeader(title: 'Department Activity (Knowledge Graph)'),
                        ...departmentList.map((raw) {
                          final d = raw as Map<String, dynamic>;
                          return Card(
                            margin: const EdgeInsets.only(bottom: 8),
                            child: ListTile(
                              leading: const Icon(Icons.account_tree_outlined),
                              title: Text(d['name']?.toString() ?? 'Department'),
                              subtitle: Text(
                                  'Officers: ${d['officer_count'] ?? '—'} · Documents: ${d['document_count'] ?? '—'} · Cases: ${d['case_count'] ?? '—'}'),
                            ),
                          );
                        }),
                      ],
                    ],
                  ),
                ),
    );
  }
}
