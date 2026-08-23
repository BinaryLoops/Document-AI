import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../core/constants.dart';
import '../../providers/auth_provider.dart';
import '../../widgets/common_widgets.dart';

/// Single adaptive login screen serving all four portals with role-specific
/// fields and authentication flow (Phase 9): citizen = Aadhaar + phone OTP;
/// government/admin/issuing-authority = Employee ID + password + MFA.
class LoginScreen extends StatefulWidget {
  final UserRole role;
  const LoginScreen({super.key, required this.role});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _aadhaarCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _employeeIdCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _departmentCtrl = TextEditingController();

  bool _loading = false;
  bool _obscure = true;

  bool get _isCitizen => widget.role == UserRole.citizen;
  bool get _isIssuingAuthority => widget.role == UserRole.issuingAuthority;

  @override
  void dispose() {
    _aadhaarCtrl.dispose();
    _phoneCtrl.dispose();
    _employeeIdCtrl.dispose();
    _passwordCtrl.dispose();
    _departmentCtrl.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _loading = true);
    try {
      final auth = context.read<AuthProvider>();
      final fields = _isCitizen
          ? {'aadhaar_number': _aadhaarCtrl.text.trim(), 'phone': _phoneCtrl.text.trim()}
          : {
              'employee_id': _employeeIdCtrl.text.trim(),
              'password': _passwordCtrl.text,
              if (_isIssuingAuthority) 'department_code': _departmentCtrl.text.trim(),
            };
      final result = await auth.login(widget.role, fields);
      if (!mounted) return;
      switch (result['next']) {
        case 'otp':
          Navigator.of(context).pushNamed('/otp-verify');
          break;
        case 'mfa':
          Navigator.of(context).pushNamed('/mfa-verify');
          break;
        default:
          _goToDashboard();
      }
    } catch (e) {
      if (mounted) showErrorSnackbar(context, e);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _goToDashboard() {
    switch (widget.role) {
      case UserRole.citizen:
        Navigator.of(context).pushNamedAndRemoveUntil('/citizen', (r) => false);
        break;
      case UserRole.governmentOfficial:
        Navigator.of(context).pushNamedAndRemoveUntil('/government', (r) => false);
        break;
      case UserRole.systemAdmin:
        Navigator.of(context).pushNamedAndRemoveUntil('/admin', (r) => false);
        break;
      case UserRole.issuingAuthority:
        Navigator.of(context).pushNamedAndRemoveUntil('/issuing-authority', (r) => false);
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Scaffold(
      appBar: AppBar(title: Text('${widget.role.displayName} Login')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: scheme.primaryContainer.withValues(alpha: 0.4),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Row(
                    children: [
                      Icon(_isCitizen ? Icons.fingerprint_rounded : Icons.lock_person_rounded,
                          color: scheme.primary),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          _isCitizen
                              ? 'Verify with your Aadhaar-linked mobile number'
                              : 'Sign in with your official credentials. Multi-factor authentication is required.',
                          style: TextStyle(fontSize: 12.5, color: scheme.onSurfaceVariant),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 28),
                if (_isCitizen) ..._citizenFields() else ..._officialFields(),
                const SizedBox(height: 28),
                FilledButton(
                  onPressed: _loading ? null : _submit,
                  child: _loading
                      ? const SizedBox(
                          height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                      : Text(_isCitizen ? 'Send OTP' : 'Continue'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  List<Widget> _citizenFields() => [
        TextFormField(
          controller: _aadhaarCtrl,
          keyboardType: TextInputType.number,
          maxLength: 12,
          decoration: const InputDecoration(labelText: 'Aadhaar Number', prefixIcon: Icon(Icons.badge_outlined)),
          validator: (v) => (v == null || v.trim().length != 12) ? 'Enter a valid 12-digit Aadhaar number' : null,
        ),
        TextFormField(
          controller: _phoneCtrl,
          keyboardType: TextInputType.phone,
          decoration: const InputDecoration(labelText: 'Registered Mobile Number', prefixIcon: Icon(Icons.phone_outlined)),
          validator: (v) => (v == null || v.trim().length < 10) ? 'Enter a valid mobile number' : null,
        ),
      ];

  List<Widget> _officialFields() => [
        TextFormField(
          controller: _employeeIdCtrl,
          decoration: const InputDecoration(labelText: 'Employee ID', prefixIcon: Icon(Icons.badge_outlined)),
          validator: (v) => (v == null || v.trim().isEmpty) ? 'Employee ID is required' : null,
        ),
        const SizedBox(height: 16),
        if (_isIssuingAuthority) ...[
          TextFormField(
            controller: _departmentCtrl,
            decoration: const InputDecoration(
                labelText: 'Department Code', prefixIcon: Icon(Icons.apartment_outlined)),
            validator: (v) => (v == null || v.trim().isEmpty) ? 'Department code is required' : null,
          ),
          const SizedBox(height: 16),
        ],
        TextFormField(
          controller: _passwordCtrl,
          obscureText: _obscure,
          decoration: InputDecoration(
            labelText: 'Password',
            prefixIcon: const Icon(Icons.lock_outline),
            suffixIcon: IconButton(
              icon: Icon(_obscure ? Icons.visibility_outlined : Icons.visibility_off_outlined),
              onPressed: () => setState(() => _obscure = !_obscure),
            ),
          ),
          validator: (v) => (v == null || v.isEmpty) ? 'Password is required' : null,
        ),
      ];
}
