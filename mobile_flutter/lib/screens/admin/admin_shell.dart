import 'package:flutter/material.dart';

import 'admin_dashboard_screen.dart';
import 'admin_profile_screen.dart';
import 'audit_logs_screen.dart';
import 'fraud_detection_screen.dart';

/// Bottom-navigation shell for the System Admin portal.
class AdminShell extends StatefulWidget {
  const AdminShell({super.key});

  @override
  State<AdminShell> createState() => _AdminShellState();
}

class _AdminShellState extends State<AdminShell> {
  int _index = 0;

  final _screens = const [
    AdminDashboardScreen(),
    AuditLogsScreen(),
    FraudDetectionScreen(),
    AdminProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _screens),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() => _index = i),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home_rounded), label: 'Home'),
          NavigationDestination(
              icon: Icon(Icons.history_edu_outlined), selectedIcon: Icon(Icons.history_edu_rounded), label: 'Audit'),
          NavigationDestination(
              icon: Icon(Icons.gpp_maybe_outlined), selectedIcon: Icon(Icons.gpp_maybe_rounded), label: 'Fraud'),
          NavigationDestination(
              icon: Icon(Icons.person_outline_rounded), selectedIcon: Icon(Icons.person_rounded), label: 'Profile'),
        ],
      ),
    );
  }
}
