import 'package:flutter/material.dart';

import '../../services/api_service.dart';
import '../../widgets/common_widgets.dart';

/// System Admin — User Management.
///
/// This backend has no `GET /users` list endpoint, so this screen is built
/// around the real endpoints that do exist: revoking all active sessions for
/// a specific user id (`POST /auth/admin/revoke-user`), which is the
/// concrete "supervise, don't edit" administrative action available today.
class UserManagementScreen extends StatefulWidget {
  const UserManagementScreen({super.key});

  @override
  State<UserManagementScreen> createState() => _UserManagementScreenState();
}

class _UserManagementScreenState extends State<UserManagementScreen> {
  final _userIdController = TextEditingController();
  bool _revoking = false;

  Future<void> _revoke() async {
    final userId = _userIdController.text.trim();
    if (userId.isEmpty) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Revoke all sessions?'),
        content: Text('This will immediately sign out user "$userId" from every device.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Revoke')),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _revoking = true);
    try {
      await ApiService.instance.revokeUserSessions(userId);
      if (mounted) showSuccessSnackbar(context, 'All sessions revoked for $userId');
      _userIdController.clear();
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    } finally {
      if (mounted) setState(() => _revoking = false);
    }
  }

  @override
  void dispose() {
    _userIdController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('User Management')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
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
                        'This platform does not expose a full user directory API yet. Available today: '
                        'force-revoke every active session/device for a specific user (e.g. on suspected '
                        'compromise), enforcing Zero Trust session policy.',
                        style: TextStyle(fontSize: 12.5),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SectionHeader(title: 'Revoke User Sessions'),
            TextField(
              controller: _userIdController,
              decoration: const InputDecoration(
                labelText: 'User ID / Employee ID / Aadhaar',
                prefixIcon: Icon(Icons.person_search_rounded),
              ),
            ),
            const SizedBox(height: 16),
            FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: Colors.red),
              onPressed: _revoking ? null : _revoke,
              icon: _revoking
                  ? const SizedBox(height: 16, width: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                  : const Icon(Icons.block_rounded),
              label: Text(_revoking ? 'Revoking...' : 'Revoke All Sessions'),
            ),
          ],
        ),
      ),
    );
  }
}
