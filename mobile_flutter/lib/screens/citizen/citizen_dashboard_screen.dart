import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../widgets/common_widgets.dart';

class CitizenDashboardScreen extends StatelessWidget {
  const CitizenDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    return Scaffold(
      appBar: AppBar(
        title: const Text('DocuMind AI'),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () => Navigator.of(context).pushNamed('/citizen/notifications'),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () async {},
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              color: Theme.of(context).colorScheme.primary,
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Row(
                  children: [
                    CircleAvatar(
                      radius: 26,
                      backgroundColor: Colors.white.withValues(alpha: 0.2),
                      child: const Icon(Icons.person_rounded, color: Colors.white, size: 30),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('Welcome back,',
                              style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 12)),
                          Text(user?.name ?? 'Citizen',
                              style: const TextStyle(
                                  color: Colors.white, fontSize: 18, fontWeight: FontWeight.w700)),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SectionHeader(title: 'Quick Actions'),
            GridView.count(
              crossAxisCount: 3,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 10,
              crossAxisSpacing: 10,
              childAspectRatio: 0.95,
              children: [
                QuickActionCard(
                  icon: Icons.document_scanner_rounded,
                  label: 'Scan Document',
                  onTap: () => Navigator.of(context).pushNamed('/citizen/scan'),
                ),
                QuickActionCard(
                  icon: Icons.upload_file_rounded,
                  label: 'Upload Document',
                  onTap: () => Navigator.of(context).pushNamed('/citizen/upload'),
                ),
                QuickActionCard(
                  icon: Icons.folder_shared_rounded,
                  label: 'My Documents',
                  onTap: () => Navigator.of(context).pushNamed('/citizen/documents'),
                ),
                QuickActionCard(
                  icon: Icons.verified_rounded,
                  label: 'Verification\nStatus',
                  onTap: () => Navigator.of(context).pushNamed('/citizen/documents'),
                ),
                QuickActionCard(
                  icon: Icons.smart_toy_rounded,
                  label: 'AI Assistant',
                  onTap: () => Navigator.of(context).pushNamed('/citizen/assistant'),
                ),
                QuickActionCard(
                  icon: Icons.compare_arrows_rounded,
                  label: 'Compare\nDocuments',
                  onTap: () => Navigator.of(context).pushNamed('/citizen/compare'),
                ),
                QuickActionCard(
                  icon: Icons.description_rounded,
                  label: 'Generate\nDocument',
                  onTap: () => Navigator.of(context).pushNamed('/citizen/generate'),
                ),
                QuickActionCard(
                  icon: Icons.local_shipping_rounded,
                  label: 'Delivery\nTracking',
                  onTap: () => Navigator.of(context).pushNamed('/citizen/tracking'),
                ),
                QuickActionCard(
                  icon: Icons.notifications_active_rounded,
                  label: 'Notifications',
                  onTap: () => Navigator.of(context).pushNamed('/citizen/notifications'),
                ),
              ],
            ),
            const SizedBox(height: 12),
          ],
        ),
      ),
    );
  }
}
