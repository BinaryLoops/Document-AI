import 'package:flutter/material.dart';

import '../../core/constants.dart';

/// Entry point of the login flow — the user picks which of the three portals
/// (per the spec, Issuing Authority is reached via the Government portal's
/// "more roles" link, since it shares the employee-credential + MFA flow).
class RoleSelectScreen extends StatelessWidget {
  const RoleSelectScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 24),
              Icon(Icons.shield_moon_rounded, size: 48, color: scheme.primary),
              const SizedBox(height: 16),
              Text(AppConstants.appName,
                  style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
              const SizedBox(height: 4),
              Text('Select your portal to continue',
                  style: TextStyle(color: scheme.onSurfaceVariant, fontSize: 14)),
              const SizedBox(height: 32),
              Expanded(
                child: ListView(
                  children: [
                    _PortalCard(
                      icon: Icons.person_rounded,
                      title: 'Citizen',
                      subtitle: 'Access, verify and manage your documents',
                      color: scheme.primary,
                      onTap: () => Navigator.of(context)
                          .pushNamed('/login', arguments: UserRole.citizen),
                    ),
                    const SizedBox(height: 14),
                    _PortalCard(
                      icon: Icons.badge_rounded,
                      title: 'Government Official',
                      subtitle: 'Case verification & jurisdiction workflows',
                      color: const Color(0xFF1B8A5A),
                      onTap: () => Navigator.of(context)
                          .pushNamed('/login', arguments: UserRole.governmentOfficial),
                    ),
                    const SizedBox(height: 14),
                    _PortalCard(
                      icon: Icons.admin_panel_settings_rounded,
                      title: 'System Admin',
                      subtitle: 'Platform oversight & analytics',
                      color: const Color(0xFF6D28D9),
                      onTap: () => Navigator.of(context)
                          .pushNamed('/login', arguments: UserRole.systemAdmin),
                    ),
                    const SizedBox(height: 14),
                    _PortalCard(
                      icon: Icons.verified_user_rounded,
                      title: 'Issuing Authority',
                      subtitle: 'Passport Office · RTO · Registrar · Revenue Dept.',
                      color: const Color(0xFFC62828),
                      onTap: () => Navigator.of(context)
                          .pushNamed('/login', arguments: UserRole.issuingAuthority),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Text(
                  'Secured with JWT · AES-256 · RBAC · Zero Trust',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: scheme.outline, fontSize: 11),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PortalCard extends StatelessWidget {
  final IconData icon;
  final String title;
  final String subtitle;
  final Color color;
  final VoidCallback onTap;

  const _PortalCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.color,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(color: color.withValues(alpha: 0.12), shape: BoxShape.circle),
                child: Icon(icon, color: color, size: 26),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15.5)),
                    const SizedBox(height: 2),
                    Text(subtitle,
                        style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 12.5)),
                  ],
                ),
              ),
              Icon(Icons.chevron_right_rounded, color: Theme.of(context).colorScheme.outline),
            ],
          ),
        ),
      ),
    );
  }
}
