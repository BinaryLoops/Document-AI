import 'package:flutter/material.dart';

import 'issue_document_screen.dart';
import 'issuing_dashboard_screen.dart';
import 'issuing_profile_screen.dart';
import 'pending_requests_screen.dart';

/// Bottom-navigation shell for the Issuing Authority portal.
class IssuingShell extends StatefulWidget {
  const IssuingShell({super.key});

  @override
  State<IssuingShell> createState() => _IssuingShellState();
}

class _IssuingShellState extends State<IssuingShell> {
  int _index = 0;

  final _screens = const [
    IssuingDashboardScreen(),
    PendingRequestsScreen(),
    IssueDocumentScreen(),
    IssuingProfileScreen(),
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
          NavigationDestination(icon: Icon(Icons.inbox_outlined), selectedIcon: Icon(Icons.inbox_rounded), label: 'Requests'),
          NavigationDestination(icon: Icon(Icons.edit_document), selectedIcon: Icon(Icons.edit_document), label: 'Issue'),
          NavigationDestination(
              icon: Icon(Icons.person_outline_rounded), selectedIcon: Icon(Icons.person_rounded), label: 'Profile'),
        ],
      ),
    );
  }
}
