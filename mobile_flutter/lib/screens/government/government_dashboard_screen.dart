import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../providers/auth_provider.dart';
import '../../widgets/common_widgets.dart';
import 'ai_summary_screen.dart';
import 'assigned_cases_screen.dart';
import 'citizen_search_screen.dart';
import 'knowledge_graph_screen.dart';
import 'reports_screen.dart';
import 'upload_case_file_screen.dart';
import 'verification_queue_screen.dart';

class GovernmentDashboardScreen extends StatelessWidget {
  const GovernmentDashboardScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    return Scaffold(
      appBar: AppBar(title: const Text('Government Portal')),
      body: ListView(
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
                    child: const Icon(Icons.badge_rounded, color: Colors.white, size: 28),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(user?.name ?? 'Officer',
                            style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w700)),
                        if (user?.jurisdiction != null)
                          Text('Jurisdiction: ${user!.jurisdiction}',
                              style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 12)),
                        if (user?.employeeId != null)
                          Text('ID: ${user!.employeeId}',
                              style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 12)),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SectionHeader(title: 'Case Management'),
          GridView.count(
            crossAxisCount: 3,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 12,
            crossAxisSpacing: 12,
            childAspectRatio: 1.08,
            children: [
              QuickActionCard(
                icon: Icons.assignment_rounded,
                label: 'Assigned\nCases',
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AssignedCasesScreen())),
              ),
              QuickActionCard(
                icon: Icons.person_search_rounded,
                label: 'Citizen\nSearch',
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const CitizenSearchScreen())),
              ),
              QuickActionCard(
                icon: Icons.fact_check_rounded,
                label: 'Verification\nQueue',
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const VerificationQueueScreen())),
              ),
              QuickActionCard(
                icon: Icons.upload_file_rounded,
                label: 'Upload\nCase File',
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const UploadCaseFileScreen())),
              ),
              QuickActionCard(
                icon: Icons.auto_awesome_rounded,
                label: 'AI Summary',
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const AiSummaryScreen())),
              ),
              QuickActionCard(
                icon: Icons.hub_rounded,
                label: 'Knowledge\nGraph',
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const KnowledgeGraphScreen())),
              ),
              QuickActionCard(
                icon: Icons.bar_chart_rounded,
                label: 'Reports',
                onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ReportsScreen())),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
