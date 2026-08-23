import 'package:flutter/foundation.dart';

import '../core/constants.dart';
import '../models/user_model.dart';
import '../services/api_client.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

enum AuthStatus { unknown, authenticated, unauthenticated }

/// Holds the current session (token presence + cached profile) and exposes
/// the multi-step login flows (citizen OTP / official-admin-issuer MFA).
class AuthProvider extends ChangeNotifier {
  AuthStatus status = AuthStatus.unknown;
  UserModel? currentUser;

  String? _pendingSessionToken;
  String? _pendingOtpId;
  String? _pendingDevOtp;
  UserRole? _pendingRole;

  Future<void> bootstrap() async {
    final token = await StorageService.instance.getAccessToken();
    if (token == null || token.isEmpty) {
      status = AuthStatus.unauthenticated;
      notifyListeners();
      return;
    }
    if (token == AppConstants.offlineDemoToken) {
      final cached = await StorageService.instance.getUserProfile();
      if (cached != null) {
        currentUser = UserModel.fromJson(cached);
        status = AuthStatus.authenticated;
      } else {
        status = AuthStatus.unauthenticated;
      }
      notifyListeners();
      return;
    }
    try {
      final profile = await ApiService.instance.me();
      currentUser = UserModel.fromJson(profile);
      await StorageService.instance.saveUserProfile(profile);
      status = AuthStatus.authenticated;
    } catch (error) {
      final isAuthorizationFailure =
          error is ApiException &&
          (error.statusCode == 401 || error.statusCode == 403);
      if (isAuthorizationFailure) {
        await StorageService.instance.clearSession();
        status = AuthStatus.unauthenticated;
        notifyListeners();
        return;
      }
      final cached = await StorageService.instance.getUserProfile();
      if (cached != null) {
        currentUser = UserModel.fromJson(cached);
        status = AuthStatus.authenticated;
      } else {
        status = AuthStatus.unauthenticated;
      }
    }
    notifyListeners();
  }

  /// Step 1 login. Returns a map describing what happens next:
  ///  {'next': 'otp'} for citizens, {'next': 'mfa'} for gov/admin/issuer,
  ///  {'next': 'done'} if the backend short-circuits straight to tokens.
  Future<Map<String, dynamic>> login(
    UserRole role,
    Map<String, dynamic> fields,
  ) async {
    Map<String, dynamic> result;
    try {
      result = await ApiService.instance.login(
        role: role.apiValue,
        fields: fields,
      );
    } on ApiException {
      final offlineProfile = _offlineDemoProfile(role, fields);
      if (offlineProfile == null) rethrow;
      await StorageService.instance.saveTokens(
        accessToken: AppConstants.offlineDemoToken,
      );
      await _completeLogin(offlineProfile);
      return {'next': 'done', 'offline': true};
    }
    _pendingRole = role;
    _pendingSessionToken = result['session_token']?.toString();
    _pendingOtpId = result['otp_id']?.toString();
    _pendingDevOtp = result['dev_otp']?.toString();

    if (result['access_token'] != null) {
      await _completeLogin(result);
      return {'next': 'done'};
    }
    final next = role == UserRole.citizen ? 'otp' : 'mfa';
    return {'next': next, ...result};
  }

  Map<String, dynamic>? _offlineDemoProfile(
    UserRole role,
    Map<String, dynamic> fields,
  ) {
    if (role == UserRole.citizen &&
        fields['aadhaar_number'] == '123456789012' &&
        fields['phone'] == '+919876543210') {
      return {
        'user_id': 'demo-citizen-001',
        'full_name': 'Ravi Kumar (Demo Citizen)',
        'role': 'citizen',
        'phone': '+919876543210',
      };
    }

    const demos = {
      'government_official': {
        'employee_id': 'GOV-MH-10042',
        'password': 'Official@1234',
        'user_id': 'demo-official-001',
        'full_name': 'Priya Sharma (Demo Official)',
        'department_code': 'REVENUE-MH',
        'role': 'government_official',
      },
      'system_admin': {
        'employee_id': 'ADMIN-001',
        'password': 'Admin@9999',
        'user_id': 'demo-admin-001',
        'full_name': 'Admin User (Demo)',
        'role': 'system_admin',
      },
      'issuing_authority': {
        'employee_id': 'ISS-PUNE-001',
        'password': 'IssAuth@5678',
        'user_id': 'demo-issauth-001',
        'full_name': 'District Collector Office (Demo)',
        'department_code': 'COLLECTOR-PUNE',
        'role': 'issuing_authority',
      },
    };

    final demo = demos[role.apiValue];
    if (demo == null ||
        fields['employee_id'] != demo['employee_id'] ||
        fields['password'] != demo['password']) {
      return null;
    }
    return Map<String, dynamic>.from(demo)..remove('password');
  }

  Future<void> confirmOtp(String otp) async {
    final otpId = _pendingOtpId;
    if (otpId == null || otpId.isEmpty) {
      throw StateError('OTP session expired. Please request a new OTP.');
    }
    final result = await ApiService.instance.verifyOtp(otpId: otpId, code: otp);
    await _completeLogin(result);
  }

  Future<void> confirmMfa(String code) async {
    final result = await ApiService.instance.verifyMfa(
      sessionToken: _pendingSessionToken ?? '',
      code: code,
    );
    await _completeLogin(result);
  }

  Future<void> _completeLogin(Map<String, dynamic> result) async {
    final profile = (result['user'] as Map?)?.cast<String, dynamic>() ?? result;
    currentUser = UserModel.fromJson(profile);
    await StorageService.instance.saveUserProfile(profile);
    await StorageService.instance.saveRole(currentUser!.role.apiValue);
    status = AuthStatus.authenticated;
    notifyListeners();
  }

  Future<void> logout() async {
    try {
      await ApiService.instance.logout();
    } catch (_) {
      await StorageService.instance.clearSession();
    }
    currentUser = null;
    status = AuthStatus.unauthenticated;
    notifyListeners();
  }

  UserRole? get pendingRole => _pendingRole;

  String? get pendingDevOtp => _pendingDevOtp;
}
