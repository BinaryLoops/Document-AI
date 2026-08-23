import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../widgets/common_widgets.dart';
import 'analytics_screen.dart';
import 'audit_logs_screen.dart';
import 'department_management_screen.dart';
import 'fraud_detection_screen.dart';
import 'user_management_screen.dart';

class AdminDashboardScreen extends StatelessWidget {
  const AdminDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    return Scaffold(
      appBar: AppBar(title: const Text('System Admin')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            color: const Color(0xFF6D28D9),
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 26,
                    backgroundColor: Colors.white.withValues(alpha: 0.2),
                    child: const Icon(Icons.admin_panel_settings_rounded, color: Colors.white, size: 28),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(user?.name ?? 'Admin',
                            style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w700)),
                        Text('System Administrator', style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 12)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Card(
              color: Colors.amber.withValues(alpha: 0.1),
              child: const Padding(
                padding: EdgeInsets.all(12),
                child: Row(
                  children: [
                    Icon(Icons.shield_moon_rounded, size: 18, color: Colors.amber),
                    SizedBox(width: 8),
                    Expanded(
                      child: Text('Admins supervise the platform — only Issuing Authorities may generate, sign, or revoke documents.',
                          style: TextStyle(fontSize: 11.5)),
                    ),
                  ],
                ),
              ),
            ),
          ),
          const SectionHeader(title: 'Platform Oversight'),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 10,
            crossAxisSpacing: 10,
            childAspectRatio: 1.5,
            children: [
              QuickActionCard(
                icon: Icons.insights_rounded,
                label: 'System Analytics',
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AnalyticsScreen())),
              ),
              QuickActionCard(
                icon: Icons.apartment_rounded,
                label: 'Department Management',
                onTap: () =>
                    Navigator.of(context).push(MaterialPageRoute(builder: (_) => const DepartmentManagementScreen())),
              ),
              QuickActionCard(
                icon: Icons.history_edu_rounded,
                label: 'Audit Logs',
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AuditLogsScreen())),
              ),
              QuickActionCard(
                icon: Icons.gpp_maybe_rounded,
                label: 'Fraud Detection',
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const FraudDetectionScreen())),
              ),
              QuickActionCard(
                icon: Icons.manage_accounts_rounded,
                label: 'User Management',
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const UserManagementScreen())),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
