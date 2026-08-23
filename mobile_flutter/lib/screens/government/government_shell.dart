import 'package:flutter/material.dart';

import 'government_dashboard_screen.dart';
import 'government_profile_screen.dart';
import 'knowledge_graph_screen.dart';
import 'reports_screen.dart';
import 'verification_queue_screen.dart';

/// Bottom-navigation shell for the Government Official portal.
class GovernmentShell extends StatefulWidget {
  const GovernmentShell({super.key});

  @override
  State<GovernmentShell> createState() => _GovernmentShellState();
}

class _GovernmentShellState extends State<GovernmentShell> {
  int _index = 0;

  final _screens = const [
    GovernmentDashboardScreen(),
    VerificationQueueScreen(),
    KnowledgeGraphScreen(),
    ReportsScreen(),
    GovernmentProfileScreen(),
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
              icon: Icon(Icons.fact_check_outlined), selectedIcon: Icon(Icons.fact_check_rounded), label: 'Queue'),
          NavigationDestination(icon: Icon(Icons.hub_outlined), selectedIcon: Icon(Icons.hub_rounded), label: 'Graph'),
          NavigationDestination(
              icon: Icon(Icons.bar_chart_outlined), selectedIcon: Icon(Icons.bar_chart_rounded), label: 'Reports'),
          NavigationDestination(
              icon: Icon(Icons.person_outline_rounded), selectedIcon: Icon(Icons.person_rounded), label: 'Profile'),
        ],
      ),
    );
  }
}
