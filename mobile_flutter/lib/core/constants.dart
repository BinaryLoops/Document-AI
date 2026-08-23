/// App-wide constants: API configuration, storage keys, and static enums.
class AppConstants {
  AppConstants._();

  static const String appName = 'DocuMind AI';
  static const String appTagline = 'Government Document Intelligence Platform';

  /// Base URL of the FastAPI backend.
  ///
  /// - Android emulator -> host machine loopback is `10.0.2.2`.
  /// - Physical device / iOS simulator -> replace with your machine's LAN IP
  ///   or a deployed backend URL (see docs/DEPLOYMENT.md).
  ///
  /// Override at build/run time with:
  ///   flutter run --dart-define=API_BASE_URL=http://192.168.1.10:8000
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  static const Duration apiConnectTimeout = Duration(seconds: 15);
  static const Duration apiReceiveTimeout = Duration(seconds: 30);
  static const Duration apiUploadTimeout = Duration(seconds: 90);

  // Secure storage keys
  static const String keyAccessToken = 'access_token';
  static const String keyRefreshToken = 'refresh_token';
  static const String keyUserRole = 'user_role';
  static const String keyUserProfile = 'user_profile';
  static const String keyThemeMode = 'theme_mode';

  // Offline queue
  static const String offlineQueueBox = 'offline_queue.db';
}

/// The four user roles supported by the backend's RBAC model.
enum UserRole { citizen, governmentOfficial, systemAdmin, issuingAuthority }

extension UserRoleX on UserRole {
  String get apiValue {
    switch (this) {
      case UserRole.citizen:
        return 'citizen';
      case UserRole.governmentOfficial:
        return 'government_official';
      case UserRole.systemAdmin:
        return 'system_admin';
      case UserRole.issuingAuthority:
        return 'issuing_authority';
    }
  }

  String get displayName {
    switch (this) {
      case UserRole.citizen:
        return 'Citizen';
      case UserRole.governmentOfficial:
        return 'Government Official';
      case UserRole.systemAdmin:
        return 'System Admin';
      case UserRole.issuingAuthority:
        return 'Issuing Authority';
    }
  }

  static UserRole fromApiValue(String value) {
    switch (value) {
      case 'government_official':
        return UserRole.governmentOfficial;
      case 'system_admin':
        return UserRole.systemAdmin;
      case 'issuing_authority':
        return UserRole.issuingAuthority;
      case 'citizen':
      default:
        return UserRole.citizen;
    }
  }
}

/// Trust badge levels returned by the verification engine.
enum TrustBadge { green, yellow, red, unknown }

extension TrustBadgeX on TrustBadge {
  static TrustBadge fromString(String? value) {
    switch (value?.toLowerCase()) {
      case 'green':
        return TrustBadge.green;
      case 'yellow':
        return TrustBadge.yellow;
      case 'red':
        return TrustBadge.red;
      default:
        return TrustBadge.unknown;
    }
  }

  String get label {
    switch (this) {
      case TrustBadge.green:
        return 'Verified';
      case TrustBadge.yellow:
        return 'Needs Review';
      case TrustBadge.red:
        return 'Rejected';
      case TrustBadge.unknown:
        return 'Pending';
    }
  }
}

/// Government document types supported by the generation engine.
enum GovDocumentType { passport, license, birth, income, land }

extension GovDocumentTypeX on GovDocumentType {
  String get apiPath {
    switch (this) {
      case GovDocumentType.passport:
        return 'passport';
      case GovDocumentType.license:
        return 'license';
      case GovDocumentType.birth:
        return 'birth';
      case GovDocumentType.income:
        return 'income';
      case GovDocumentType.land:
        return 'land';
    }
  }

  String get displayName {
    switch (this) {
      case GovDocumentType.passport:
        return 'Passport';
      case GovDocumentType.license:
        return 'Driving Licence';
      case GovDocumentType.birth:
        return 'Birth Certificate';
      case GovDocumentType.income:
        return 'Income Certificate';
      case GovDocumentType.land:
        return 'Land Record';
    }
  }
}
