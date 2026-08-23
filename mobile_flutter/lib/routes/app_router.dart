import 'package:flutter/material.dart';

import '../core/constants.dart';
import '../screens/admin/admin_shell.dart';
import '../screens/auth/login_screen.dart';
import '../screens/auth/mfa_screen.dart';
import '../screens/auth/otp_screen.dart';
import '../screens/auth/role_select_screen.dart';
import '../screens/citizen/ai_assistant_screen.dart';
import '../screens/citizen/citizen_shell.dart';
import '../screens/citizen/compare_documents_screen.dart';
import '../screens/citizen/document_detail_screen.dart';
import '../screens/citizen/generate_document_screen.dart';
import '../screens/citizen/my_documents_screen.dart';
import '../screens/citizen/notifications_screen.dart';
import '../screens/citizen/scan_document_screen.dart';
import '../screens/citizen/tracking_screen.dart';
import '../screens/citizen/upload_document_screen.dart';
import '../screens/government/government_shell.dart';
import '../screens/issuing_authority/issuing_shell.dart';
import '../screens/splash/splash_screen.dart';

/// Central route table for the whole app (Phase 2/10). Every navigation in
/// the app goes through named routes generated here so the flow stays easy
/// to audit against the PS23 spec.
class AppRouter {
  AppRouter._();

  static Route<dynamic> onGenerateRoute(RouteSettings settings) {
    switch (settings.name) {
      case '/':
      case '/splash':
        return _page(const SplashScreen());

      case '/role-select':
        return _page(const RoleSelectScreen());

      case '/login':
        final role = settings.arguments as UserRole? ?? UserRole.citizen;
        return _page(LoginScreen(role: role));

      case '/otp-verify':
        return _page(const OtpScreen());

      case '/mfa-verify':
        return _page(const MfaScreen());

      // ---- Citizen portal ----
      case '/citizen':
        return _page(const CitizenShell());
      case '/citizen/scan':
        return _page(const ScanDocumentScreen());
      case '/citizen/upload':
        return _page(const UploadDocumentScreen());
      case '/citizen/documents':
        return _page(const MyDocumentsScreen());
      case '/citizen/document-detail':
        final documentId = settings.arguments as String;
        return _page(DocumentDetailScreen(documentId: documentId));
      case '/citizen/assistant':
        return _page(const AiAssistantScreen());
      case '/citizen/compare':
        return _page(const CompareDocumentsScreen());
      case '/citizen/generate':
        return _page(const GenerateDocumentScreen());
      case '/citizen/notifications':
        return _page(const NotificationsScreen());
      case '/citizen/tracking':
        final applicationId = settings.arguments as String?;
        return _page(TrackingScreen(applicationId: applicationId));

      // ---- Government portal ----
      case '/government':
        return _page(const GovernmentShell());

      // ---- Admin portal ----
      case '/admin':
        return _page(const AdminShell());

      // ---- Issuing authority portal ----
      case '/issuing-authority':
        return _page(const IssuingShell());

      default:
        return _page(Scaffold(
          body: Center(child: Text('Route not found: ${settings.name}')),
        ));
    }
  }

  static MaterialPageRoute _page(Widget child) => MaterialPageRoute(builder: (_) => child);
}
