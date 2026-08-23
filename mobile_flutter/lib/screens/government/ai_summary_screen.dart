import 'package:flutter/material.dart';

import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// Government Official — AI Summary (`POST /ai/summarize`). Paste or type a
/// document's extracted text to get key points, dates/deadlines, orgs and
/// people — useful when reviewing a case file's contents quickly.
class AiSummaryScreen extends StatefulWidget {
  const AiSummaryScreen({super.key});

  @override
  State<AiSummaryScreen> createState() => _AiSummaryScreenState();
}

class _AiSummaryScreenState extends State<AiSummaryScreen> {
  final _textController = TextEditingController();
  bool _loading = false;
  Map<String, dynamic>? _result;
  String? _error;

  Future<void> _summarize() async {
    final text = _textController.text.trim();
    if (text.isEmpty) return;
    setState(() {
      _loading = true;
      _error = null;
      _result = null;
    });
    try {
      final result = await ApiService.instance.summarize(text);
      setState(() => _result = result);
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('ApiException: ', ''));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('AI Summary')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Paste the document text you want summarised',
                style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 13)),
            const SizedBox(height: 10),
            TextField(
              controller: _textController,
              maxLines: 8,
              decoration: const InputDecoration(hintText: 'Paste document text here...', alignLabelWithHint: true),
            ),
            const SizedBox(height: 14),
            FilledButton.icon(
              onPressed: _loading ? null : _summarize,
              icon: _loading
                  ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.auto_awesome_rounded),
              label: Text(_loading ? 'Summarizing...' : 'Summarize'),
            ),
            if (_error != null) ...[
              const SizedBox(height: 16),
              EmptyState(icon: Icons.error_outline_rounded, title: 'Could not summarize', subtitle: _error!),
            ],
            if (_result != null) ..._buildResult(context, _result!),
          ],
        ),
      ),
    );
  }

  List<Widget> _buildResult(BuildContext context, Map<String, dynamic> result) {
    final summary = result['summary']?.toString() ?? result['key_points']?.toString();
    final dates = (result['dates'] as List?) ?? (result['deadlines'] as List?) ?? [];
    final orgs = (result['organizations'] as List?) ?? (result['orgs'] as List?) ?? [];
    final people = (result['people'] as List?) ?? [];

    return [
      const SectionHeader(title: 'Summary'),
      Card(child: Padding(padding: const EdgeInsets.all(16), child: Text(summary ?? result.toString()))),
      if (dates.isNotEmpty) _buildChipSection(context, 'Dates & Deadlines', dates, Icons.event_rounded),
      if (orgs.isNotEmpty) _buildChipSection(context, 'Organizations', orgs, Icons.apartment_rounded),
      if (people.isNotEmpty) _buildChipSection(context, 'People', people, Icons.person_rounded),
    ];
  }

  Widget _buildChipSection(BuildContext context, String title, List items, IconData icon) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SectionHeader(title: title),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: items.map((i) => Chip(avatar: Icon(icon, size: 16), label: Text(i.toString()))).toList(),
        ),
      ],
    );
  }
}
