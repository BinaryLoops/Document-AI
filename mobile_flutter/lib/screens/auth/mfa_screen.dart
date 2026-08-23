import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/constants.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/common_widgets.dart';

/// Step 2 for Government Official / System Admin / Issuing Authority —
/// TOTP multi-factor authentication code (RFC 6238) or a backup code.
class MfaScreen extends StatefulWidget {
  const MfaScreen({super.key});

  @override
  State<MfaScreen> createState() => _MfaScreenState();
}

class _MfaScreenState extends State<MfaScreen> {
  final _codeCtrl = TextEditingController();
  bool _loading = false;

  Future<void> _verify() async {
    if (_codeCtrl.text.trim().isEmpty) return;
    setState(() => _loading = true);
    try {
      final auth = context.read<AuthProvider>();
      await auth.confirmMfa(_codeCtrl.text.trim());
      if (!mounted) return;
      final role = auth.currentUser?.role ?? auth.pendingRole ?? UserRole.governmentOfficial;
      final route = switch (role) {
        UserRole.governmentOfficial => '/government',
        UserRole.systemAdmin => '/admin',
        UserRole.issuingAuthority => '/issuing-authority',
        UserRole.citizen => '/citizen',
      };
      Navigator.of(context).pushNamedAndRemoveUntil(route, (r) => false);
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Multi-Factor Authentication')),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(Icons.security_rounded, size: 42, color: Theme.of(context).colorScheme.primary),
              const SizedBox(height: 16),
              const Text('Enter your authenticator code',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
              const SizedBox(height: 6),
              Text(
                'Open your authenticator app and enter the 6-digit TOTP code, or use a backup code.',
                style: TextStyle(color: Theme.of(context).colorScheme.onSurfaceVariant, fontSize: 13),
              ),
              const SizedBox(height: 28),
              TextField(
                controller: _codeCtrl,
                keyboardType: TextInputType.text,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 22, letterSpacing: 6, fontWeight: FontWeight.bold),
                decoration: const InputDecoration(hintText: '••••••'),
              ),
              const SizedBox(height: 16),
              FilledButton(
                onPressed: _loading ? null : _verify,
                child: _loading
                    ? const SizedBox(
                        height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Text('Verify & Sign In'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
