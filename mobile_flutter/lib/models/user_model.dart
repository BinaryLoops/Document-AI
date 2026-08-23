import '../core/constants.dart';

/// Authenticated user profile, as returned by `GET /auth/me`.
class UserModel {
  final String id;
  final String name;
  final UserRole role;
  final String? aadhaarMasked;
  final String? phone;
  final String? employeeId;
  final String? departmentCode;
  final String? jurisdiction;
  final bool mfaEnabled;
  final List<String> permissions;

  UserModel({
    required this.id,
    required this.name,
    required this.role,
    this.aadhaarMasked,
    this.phone,
    this.employeeId,
    this.departmentCode,
    this.jurisdiction,
    this.mfaEnabled = false,
    this.permissions = const [],
  });

  factory UserModel.fromJson(Map<String, dynamic> json) {
    return UserModel(
      id: (json['id'] ?? json['user_id'] ?? '').toString(),
      name: (json['name'] ?? json['full_name'] ?? json['display_name'] ?? 'User').toString(),
      role: UserRoleX.fromApiValue((json['role'] ?? 'citizen').toString()),
      aadhaarMasked: json['aadhaar_masked']?.toString() ?? json['aadhaar_number']?.toString(),
      phone: json['phone']?.toString(),
      employeeId: json['employee_id']?.toString(),
      departmentCode: json['department_code']?.toString(),
      jurisdiction: json['jurisdiction']?.toString(),
      mfaEnabled: json['mfa_enabled'] == true,
      permissions: (json['permissions'] as List?)?.map((e) => e.toString()).toList() ?? const [],
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'role': role.apiValue,
        'aadhaar_masked': aadhaarMasked,
        'phone': phone,
        'employee_id': employeeId,
        'department_code': departmentCode,
        'jurisdiction': jurisdiction,
        'mfa_enabled': mfaEnabled,
        'permissions': permissions,
      };
}
