import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/constants.dart';
import '../../providers/auth_provider.dart';

/// Government-style secure boot screen. Shows the app identity while the
/// session is silently validated against the backend (`GET /auth/me`).
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: const Duration(milliseconds: 900))
      ..forward();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    final auth = context.read<AuthProvider>();
    final stopwatch = Stopwatch()..start();
    await auth.bootstrap();
    final elapsed = stopwatch.elapsedMilliseconds;
    // Keep the splash visible for a minimum, deliberate duration — this is a
    // security-conscious app; an instant flash reads as untrustworthy.
    if (elapsed < 1200) {
      await Future.delayed(Duration(milliseconds: 1200 - elapsed));
    }
    if (!mounted) return;
    if (auth.status == AuthStatus.authenticated) {
      _goToDashboard(auth.currentUser!.role);
    } else {
      Navigator.of(context).pushReplacementNamed('/role-select');
    }
  }

  void _goToDashboard(UserRole role) {
    switch (role) {
      case UserRole.citizen:
        Navigator.of(context).pushReplacementNamed('/citizen');
        break;
      case UserRole.governmentOfficial:
        Navigator.of(context).pushReplacementNamed('/government');
        break;
      case UserRole.systemAdmin:
        Navigator.of(context).pushReplacementNamed('/admin');
        break;
      case UserRole.issuingAuthority:
        Navigator.of(context).pushReplacementNamed('/issuing-authority');
        break;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      backgroundColor: scheme.primary,
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ScaleTransition(
              scale: CurvedAnimation(parent: _controller, curve: Curves.elasticOut),
              child: Container(
                width: 110,
                height: 110,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(28),
                  boxShadow: [
                    BoxShadow(color: Colors.black.withValues(alpha: 0.2), blurRadius: 24, offset: const Offset(0, 8)),
                  ],
                ),
                child: Icon(Icons.shield_moon_rounded, size: 58, color: scheme.primary),
              ),
            ),
            const SizedBox(height: 24),
            FadeTransition(
              opacity: _controller,
              child: const Text(
                AppConstants.appName,
                style: TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.w800, letterSpacing: 0.5),
              ),
            ),
            const SizedBox(height: 6),
            FadeTransition(
              opacity: _controller,
              child: Text(
                AppConstants.appTagline,
                style: TextStyle(color: Colors.white.withValues(alpha: 0.85), fontSize: 13),
              ),
            ),
            const SizedBox(height: 48),
            const SizedBox(
              width: 28,
              height: 28,
              child: CircularProgressIndicator(strokeWidth: 3, valueColor: AlwaysStoppedAnimation(Colors.white)),
            ),
            const SizedBox(height: 14),
            Text('Establishing secure session...',
                style: TextStyle(color: Colors.white.withValues(alpha: 0.8), fontSize: 12)),
          ],
        ),
      ),
    );
  }
}
