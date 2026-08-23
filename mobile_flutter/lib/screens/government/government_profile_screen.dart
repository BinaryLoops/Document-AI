import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/constants.dart';
import '../../providers/auth_provider.dart';
import '../../providers/theme_provider.dart';

class GovernmentProfileScreen extends StatelessWidget {
  const GovernmentProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    final themeProvider = context.watch<ThemeProvider>();
    final user = auth.currentUser;
    return Scaffold(
      appBar: AppBar(title: const Text('Profile')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Center(
            child: Column(
              children: [
                CircleAvatar(
                  radius: 42,
                  backgroundColor: Theme.of(context).colorScheme.primaryContainer,
                  child: const Icon(Icons.badge_rounded, size: 40),
                ),
                const SizedBox(height: 12),
                Text(user?.name ?? 'Officer', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                Text(user?.role.displayName ?? '', style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant)),
              ],
            ),
          ),
          const SizedBox(height: 24),
          Card(
            child: Column(
              children: [
                if (user?.employeeId != null)
                  ListTile(leading: const Icon(Icons.work_outline), title: const Text('Employee ID'), subtitle: Text(user!.employeeId!)),
                if (user?.jurisdiction != null)
                  ListTile(leading: const Icon(Icons.map_outlined), title: const Text('Jurisdiction'), subtitle: Text(user!.jurisdiction!)),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Card(
            child: SwitchListTile(
              secondary: const Icon(Icons.dark_mode_outlined),
              title: const Text('Dark Mode'),
              value: themeProvider.mode == ThemeMode.dark,
              onChanged: (_) => themeProvider.toggle(),
            ),
          ),
          const SizedBox(height: 24),
          OutlinedButton.icon(
            style: OutlinedButton.styleFrom(foregroundColor: Colors.red),
            onPressed: () async {
              await auth.logout();
              if (context.mounted) {
                Navigator.of(context).pushNamedAndRemoveUntil('/role-select', (r) => false);
              }
            },
            icon: const Icon(Icons.logout_rounded),
            label: const Text('Sign Out'),
          ),
        ],
      ),
    );
  }
}
