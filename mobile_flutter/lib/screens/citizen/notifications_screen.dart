import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';

import '../../models/notification_model.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  late Future<List<NotificationModel>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<NotificationModel>> _load() async {
    final userId = context.read<AuthProvider>().currentUser?.id ?? '';
    final raw = await ApiService.instance.notifications(userId);
    return raw.map((e) => NotificationModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<void> _markAllRead(List<NotificationModel> items) async {
    final unread = items.where((n) => !n.read).map((n) => n.id).toList();
    if (unread.isEmpty) return;
    try {
      await ApiService.instance.markNotificationsRead(unread);
      setState(() => _future = _load());
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          FutureBuilder<List<NotificationModel>>(
            future: _future,
            builder: (context, snapshot) => TextButton(
              onPressed: snapshot.hasData ? () => _markAllRead(snapshot.data!) : null,
              child: const Text('Mark all read'),
            ),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {
          setState(() => _future = _load());
          await _future;
        },
        child: FutureBuilder<List<NotificationModel>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            final items = snapshot.data ?? [];
            if (items.isEmpty) {
              return ListView(children: const [
                EmptyState(
                  icon: Icons.notifications_off_outlined,
                  title: 'No notifications',
                  subtitle: 'You are all caught up.',
                ),
              ]);
            }
            return ListView.separated(
              itemCount: items.length,
              separatorBuilder: (_, _) => const Divider(height: 1),
              itemBuilder: (context, index) {
                final n = items[index];
                return ListTile(
                  leading: Icon(
                    n.read ? Icons.notifications_none_rounded : Icons.notifications_active_rounded,
                    color: n.read ? null : Theme.of(context).colorScheme.primary,
                  ),
                  title: Text(n.title, style: TextStyle(fontWeight: n.read ? FontWeight.normal : FontWeight.bold)),
                  subtitle: Text(n.message),
                  trailing: Text(DateFormat('MMM d').format(n.createdAt), style: const TextStyle(fontSize: 11)),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
