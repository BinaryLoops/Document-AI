import 'package:flutter/material.dart';

import '../../models/document_model.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

class CompareDocumentsScreen extends StatefulWidget {
  const CompareDocumentsScreen({super.key});

  @override
  State<CompareDocumentsScreen> createState() => _CompareDocumentsScreenState();
}

class _CompareDocumentsScreenState extends State<CompareDocumentsScreen> {
  late Future<List<DocumentModel>> _future;
  final Set<String> _selected = {};
  Map<String, dynamic>? _result;
  bool _comparing = false;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<DocumentModel>> _load() async {
    final raw = await ApiService.instance.listDocuments();
    return raw.map((e) => DocumentModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> _compare() async {
    if (_selected.length < 2) return;
    setState(() {
      _comparing = true;
      _result = null;
    });
    try {
      final result = await ApiService.instance.compareDocuments(_selected.toList());
      setState(() => _result = result);
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    } finally {
      if (mounted) setState(() => _comparing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Compare Documents')),
      body: FutureBuilder<List<DocumentModel>>(
        future: _future,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          final docs = snapshot.data ?? [];
          if (docs.length < 2) {
            return const EmptyState(
              icon: Icons.compare_arrows_rounded,
              title: 'Not enough documents',
              subtitle: 'Upload at least two documents to compare them for inconsistencies.',
            );
          }
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              const Text('Select 2 or more documents to compare',
                  style: TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 10),
              ...docs.map((d) => CheckboxListTile(
                    value: _selected.contains(d.id),
                    title: Text(d.filename),
                    subtitle: Text(d.category ?? ''),
                    onChanged: (checked) => setState(() {
                      if (checked == true) {
                        _selected.add(d.id);
                      } else {
                        _selected.remove(d.id);
                      }
                    }),
                  )),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: _selected.length >= 2 && !_comparing ? _compare : null,
                icon: _comparing
                    ? const SizedBox(
                        height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.compare_rounded),
                label: Text(_comparing ? 'Comparing...' : 'Compare Selected'),
              ),
              if (_result != null) ...[
                const SectionHeader(title: 'Result'),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text(
                      _result!['summary']?.toString() ?? _result.toString(),
                    ),
                  ),
                ),
                if (_result!['inconsistencies'] is List)
                  ...((_result!['inconsistencies'] as List).map((i) => Card(
                        color: Colors.orange.withValues(alpha: 0.08),
                        margin: const EdgeInsets.only(top: 8),
                        child: Padding(
                          padding: const EdgeInsets.all(12),
                          child: Text(i is Map ? (i['message']?.toString() ?? i.toString()) : i.toString()),
                        ),
                      ))),
              ],
            ],
          );
        },
      ),
    );
  }
}
