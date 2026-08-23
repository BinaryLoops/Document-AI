import 'package:flutter/material.dart';

import '../core/constants.dart';
import '../core/theme.dart';

/// Green / Yellow / Red verification trust badge used throughout the app.
class TrustBadgeChip extends StatelessWidget {
  final TrustBadge badge;
  final bool large;

  const TrustBadgeChip({super.key, required this.badge, this.large = false});

  @override
  Widget build(BuildContext context) {
    final Color color;
    final IconData icon;
    switch (badge) {
      case TrustBadge.green:
        color = AppTheme.emerald;
        icon = Icons.verified_rounded;
        break;
      case TrustBadge.yellow:
        color = AppTheme.amber;
        icon = Icons.warning_rounded;
        break;
      case TrustBadge.red:
        color = AppTheme.crimson;
        icon = Icons.cancel_rounded;
        break;
      case TrustBadge.unknown:
        color = Colors.grey;
        icon = Icons.hourglass_top_rounded;
        break;
    }

    return Container(
      padding: EdgeInsets.symmetric(horizontal: large ? 14 : 10, vertical: large ? 8 : 5),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: color.withValues(alpha: 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: large ? 18 : 14, color: color),
          const SizedBox(width: 6),
          Text(
            badge.label,
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.w700,
              fontSize: large ? 14 : 12,
            ),
          ),
        ],
      ),
    );
  }
}
