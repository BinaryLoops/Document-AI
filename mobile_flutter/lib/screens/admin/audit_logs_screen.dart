import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// System Admin — Audit Logs (`GET /security/audit`), with a tamper-detection
/// chain-integrity check (`GET /security/audit/verify`).
class AuditLogsScreen extends StatefulWidget {
  const AuditLogsScreen({super.key});

  @override
  State<AuditLogsScreen> createState() => _AuditLogsScreenState();
}

class _AuditLogsScreenState extends State<AuditLogsScreen> {
  late Future<List<dynamic>> _future;
  Map<String, dynamic>? _verifyResult;
  bool _verifying = false;

  @override
  void initState() {
    super.initState();
    _future = ApiService.instance.auditLog(limit: 100);
  }

  Future<void> _refresh() async {
    setState(() => _future = ApiService.instance.auditLog(limit: 100));
    await _future;
  }

  Future<void> _verifyChain() async {
    setState(() => _verifying = true);
    try {
      final result = await ApiService.instance.verifyAuditChain();
      setState(() => _verifyResult = result);
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    } finally {
      if (mounted) setState(() => _verifying = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Audit Logs')),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.verified_user_rounded),
                        const SizedBox(width: 10),
                        const Expanded(child: Text('Hash-chain integrity check', style: TextStyle(fontWeight: FontWeight.w700))),
                        FilledButton(onPressed: _verifying ? null : _verifyChain, child: Text(_verifying ? '...' : 'Verify')),
                      ],
                    ),
                    if (_verifyResult != null) ...[
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Icon(
                            _verifyResult!['valid'] == true ? Icons.check_circle_rounded : Icons.warning_rounded,
                            color: _verifyResult!['valid'] == true ? Colors.green : Colors.red,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(_verifyResult!['valid'] == true
                                ? 'Audit chain is intact — no tampering detected.'
                                : 'Audit chain integrity issue detected: ${_verifyResult!['message'] ?? ''}'),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SectionHeader(title: 'Recent Entries'),
            FutureBuilder<List<dynamic>>(
              future: _future,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 40),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                if (snapshot.hasError) {
                  return EmptyState(
                    icon: Icons.error_outline_rounded,
                    title: 'Could not load audit log',
                    subtitle: snapshot.error.toString().replaceFirst('ApiException: ', ''),
                  );
                }
                final entries = snapshot.data ?? [];
                if (entries.isEmpty) {
                  return const EmptyState(icon: Icons.history_rounded, title: 'No audit entries', subtitle: 'Nothing recorded yet.');
                }
                return Column(
                  children: entries.map((raw) {
                    final e = raw as Map<String, dynamic>;
                    final ts = e['timestamp']?.toString();
                    DateTime? parsed = ts != null ? DateTime.tryParse(ts) : null;
                    return Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        dense: true,
                        leading: const Icon(Icons.receipt_long_outlined),
                        title: Text(e['action']?.toString() ?? e['event']?.toString() ?? 'Event'),
                        subtitle: Text(e['actor']?.toString() ?? e['user_id']?.toString() ?? '—'),
                        trailing: parsed != null
                            ? Text(DateFormat('MMM d, HH:mm').format(parsed), style: const TextStyle(fontSize: 11))
                            : null,
                      ),
                    );
                  }).toList(),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
