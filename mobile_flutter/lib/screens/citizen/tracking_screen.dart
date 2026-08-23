import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../models/notification_model.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// Delivery / application tracking (Phase 8 continuation) — timeline view
/// of an application's progress from submission through dispatch/delivery.
class TrackingScreen extends StatefulWidget {
  final String? applicationId;
  const TrackingScreen({super.key, this.applicationId});

  @override
  State<TrackingScreen> createState() => _TrackingScreenState();
}

class _TrackingScreenState extends State<TrackingScreen> {
  final _idController = TextEditingController();
  TrackingModel? _tracking;
  bool _loading = false;
  String? _error;

  static const _stages = ['submitted', 'under_review', 'approved', 'dispatched', 'delivered'];

  @override
  void initState() {
    super.initState();
    if (widget.applicationId != null) {
      _idController.text = widget.applicationId!;
      _search();
    }
  }

  Future<void> _search() async {
    if (_idController.text.trim().isEmpty) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final result = await ApiService.instance.trackApplication(_idController.text.trim());
      setState(() => _tracking = TrackingModel.fromJson(result));
    } catch (e) {
      setState(() => _error = e.toString().replaceFirst('ApiException: ', ''));
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Delivery Tracking')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _idController,
                    decoration: const InputDecoration(labelText: 'Application / Request ID'),
                    onSubmitted: (_) => _search(),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(onPressed: _loading ? null : _search, child: const Text('Track')),
              ],
            ),
            const SizedBox(height: 20),
            if (_loading) const Center(child: CircularProgressIndicator()),
            if (_error != null)
              EmptyState(icon: Icons.search_off_rounded, title: 'Not found', subtitle: _error!),
            if (_tracking != null) Expanded(child: _buildTimeline(context, _tracking!)),
          ],
        ),
      ),
    );
  }

  Widget _buildTimeline(BuildContext context, TrackingModel tracking) {
    final currentIndex = _stages.indexOf(tracking.stage);
    return ListView(
      children: [
        for (var i = 0; i < _stages.length; i++)
          _buildStageTile(context, _stages[i], i <= currentIndex, i == currentIndex, i == _stages.length - 1),
        if (tracking.history.isNotEmpty) ...[
          const SectionHeader(title: 'History'),
          ...tracking.history.map((h) => ListTile(
                dense: true,
                leading: const Icon(Icons.circle, size: 8),
                title: Text(h.stage),
                subtitle: h.note != null ? Text(h.note!) : null,
                trailing: Text(DateFormat('MMM d, HH:mm').format(h.timestamp), style: const TextStyle(fontSize: 11)),
              )),
        ],
      ],
    );
  }

  Widget _buildStageTile(BuildContext context, String stage, bool done, bool current, bool isLast) {
    final scheme = Theme.of(context).colorScheme;
    final color = done ? scheme.primary : scheme.outlineVariant;
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Icon(done ? Icons.check_circle_rounded : Icons.radio_button_unchecked, color: color, size: 22),
              if (!isLast) Expanded(child: Container(width: 2, color: color)),
            ],
          ),
          const SizedBox(width: 12),
          Padding(
            padding: const EdgeInsets.only(bottom: 24, top: 2),
            child: Text(
              stage.replaceAll('_', ' ').toUpperCase(),
              style: TextStyle(fontWeight: current ? FontWeight.bold : FontWeight.w500, color: done ? null : scheme.outline),
            ),
          ),
        ],
      ),
    );
  }
}
