import 'dart:io';

import 'package:dio/dio.dart';

import 'api_client.dart';
import 'connectivity_service.dart';
import 'offline_queue_service.dart';
import 'storage_service.dart';

/// Centralised, single source of truth for every backend call the app makes.
///
/// No screen should call `Dio`/`http` directly — everything goes through
/// here so retry/offline/auth handling stays consistent app-wide.
class ApiService {
  ApiService._internal();
  static final ApiService instance = ApiService._internal();

  Dio get _dio => ApiClient.instance.dio;

  Future<T> _guard<T>(Future<T> Function() action) async {
    try {
      return await action();
    } catch (e) {
      throw ApiClient.normalize(e);
    }
  }

  // ===========================================================================
  // 1. System
  // ===========================================================================
  Future<Map<String, dynamic>> health() =>
      _guard(() async => (await _dio.get('/health')).data as Map<String, dynamic>);

  Future<Map<String, dynamic>> status() =>
      _guard(() async => (await _dio.get('/status')).data as Map<String, dynamic>);

  // ===========================================================================
  // 2. Authentication
  // ===========================================================================

  /// Step 1 login. Role-specific fields go in [fields], e.g.:
  ///  citizen: {aadhaar_number, phone}
  ///  official/admin/issuing_authority: {employee_id, password, department_code?}
  Future<Map<String, dynamic>> login({
    required String role,
    required Map<String, dynamic> fields,
  }) =>
      _guard(() async {
        final response = await _dio.post('/auth/login', data: {'role': role, ...fields});
        return response.data as Map<String, dynamic>;
      });

  /// Step 2 for citizens — verify the OTP sent to their phone.
  Future<Map<String, dynamic>> verifyOtp({
    required String otpId,
    required String code,
  }) =>
      _guard(() async {
        final response = await _dio.post('/auth/otp', data: {
          'otp_id': otpId,
          'code': code,
        });
        return _persistAuthResult(response.data as Map<String, dynamic>);
      });

  /// Step 2 for officials/admins/issuing authorities — TOTP or backup code.
  Future<Map<String, dynamic>> verifyMfa({
    required String sessionToken,
    required String code,
  }) =>
      _guard(() async {
        final response = await _dio.post('/auth/mfa', data: {
          'session_token': sessionToken,
          'code': code,
        });
        return _persistAuthResult(response.data as Map<String, dynamic>);
      });

  Future<Map<String, dynamic>> _persistAuthResult(Map<String, dynamic> data) async {
    final access = data['access_token']?.toString();
    final refresh = data['refresh_token']?.toString();
    if (access != null) {
      await StorageService.instance.saveTokens(accessToken: access, refreshToken: refresh);
    }
    return data;
  }

  Future<void> logout() => _guard(() async {
        try {
          await _dio.post('/auth/logout');
        } finally {
          await StorageService.instance.clearSession();
        }
      });

  Future<Map<String, dynamic>> me() =>
      _guard(() async => (await _dio.get('/auth/me')).data as Map<String, dynamic>);

  Future<List<dynamic>> loginHistory() =>
      _guard(() async => (await _dio.get('/auth/history')).data as List<dynamic>);

  Future<List<dynamic>> devices() =>
      _guard(() async => (await _dio.get('/auth/devices')).data as List<dynamic>);

  // ===========================================================================
  // 3. Digital Locker — Documents
  // ===========================================================================

  Future<Map<String, dynamic>> uploadDocument({
    required File file,
    String? category,
    String? ownerId,
  }) =>
      _guard(() async {
        if (!ConnectivityService.instance.isOnline) {
          await OfflineQueueService.instance.enqueue(QueuedRequest(
            method: 'POST',
            path: '/documents/upload',
            fields: {'category': category, 'owner': ownerId},
            filePath: file.path,
            fileFieldName: 'file',
          ));
          return {'status': 'queued', 'message': 'No connection — upload queued and will resume automatically.'};
        }
        final formData = FormData.fromMap({
          if (category != null) 'category': category,
          if (ownerId != null) 'owner': ownerId,
          'file': await MultipartFile.fromFile(file.path, filename: file.uri.pathSegments.last),
        });
        final response = await _dio.post(
          '/documents/upload',
          data: formData,
          options: Options(sendTimeout: const Duration(seconds: 90)),
        );
        return response.data as Map<String, dynamic>;
      });

  Future<List<dynamic>> listDocuments({String? ownerId, String? status}) =>
      _guard(() async {
        final response = await _dio.get('/documents', queryParameters: {
          if (ownerId != null) 'owner': ownerId,
          if (status != null) 'status': status,
        });
        final data = response.data;
        if (data is Map && data['documents'] is List) return data['documents'] as List;
        return data as List<dynamic>;
      });

  Future<Map<String, dynamic>> getDocument(String documentId) => _guard(
      () async => (await _dio.get('/documents/$documentId')).data as Map<String, dynamic>);

  Future<List<dynamic>> documentCategories() =>
      _guard(() async => (await _dio.get('/documents/categories')).data as List<dynamic>);

  Future<List<dynamic>> searchDocuments(String query) => _guard(() async {
        final response = await _dio.get('/documents/search', queryParameters: {'q': query});
        final data = response.data;
        if (data is Map && data['results'] is List) return data['results'] as List;
        return data as List<dynamic>;
      });

  Future<void> archiveDocument(String documentId) =>
      _guard(() async => _dio.post('/documents/archive', data: {'document_id': documentId}));

  Future<void> requestDelete(String documentId) => _guard(
      () async => _dio.post('/documents/request-delete', data: {'document_id': documentId}));

  String documentPreviewUrl(String documentId) =>
      '${_dio.options.baseUrl}/documents/$documentId/preview';

  String documentThumbnailUrl(String documentId) =>
      '${_dio.options.baseUrl}/documents/$documentId/thumbnail';

  // ===========================================================================
  // 4. Verification Engine
  // ===========================================================================

  Future<Map<String, dynamic>> verifyDocument({
    required String documentId,
    String? department,
  }) =>
      _guard(() async {
        final response = await _dio.post('/verify/document', data: {
          'document_id': documentId,
          if (department != null) 'department': department,
        });
        return response.data as Map<String, dynamic>;
      });

  Future<Map<String, dynamic>> verificationStatus(String verificationId) => _guard(() async =>
      (await _dio.get('/verify/status/$verificationId')).data as Map<String, dynamic>);

  Future<List<dynamic>> verificationHistory(String documentId) => _guard(
      () async => (await _dio.get('/verify/history/$documentId')).data as List<dynamic>);

  Future<List<dynamic>> pendingReviews() => _guard(() async {
        final response = await _dio.get('/verify/pending-reviews');
        final data = response.data;
        if (data is Map && data['reviews'] is List) return data['reviews'] as List<dynamic>;
        return data as List<dynamic>;
      });

  Future<void> submitManualReview({
    required String documentId,
    required String decision,
    String? notes,
  }) =>
      _guard(() async => _dio.post('/verify/manual-review', data: {
            'document_id': documentId,
            'decision': decision,
            'notes': notes,
          }));

  Future<List<dynamic>> verificationDepartments() => _guard(() async {
        final response = await _dio.get('/verify/departments');
        final data = response.data;
        if (data is Map && data['departments'] is List) return data['departments'] as List<dynamic>;
        return data as List<dynamic>;
      });

  // ===========================================================================
  // 5. AI Intelligence
  // ===========================================================================

  Future<Map<String, dynamic>> summarize(String text) => _guard(() async =>
      (await _dio.post('/ai/summarize', data: {'text': text})).data as Map<String, dynamic>);

  Future<Map<String, dynamic>> extractEntities(String text) => _guard(() async =>
      (await _dio.post('/ai/entities', data: {'text': text})).data as Map<String, dynamic>);

  Future<Map<String, dynamic>> extractTimeline(String text) => _guard(() async =>
      (await _dio.post('/ai/timeline', data: {'text': text})).data as Map<String, dynamic>);

  Future<Map<String, dynamic>> caseIntel(List<String> texts) => _guard(() async =>
      (await _dio.post('/ai/case-intel', data: {'documents': texts})).data as Map<String, dynamic>);

  /// Evidence-backed Q&A — the AI Assistant chat.
  Future<Map<String, dynamic>> assistantAsk({
    required String question,
    required String documentText,
  }) =>
      _guard(() async {
        final response = await _dio.post('/assistant/ask', data: {
          'question': question,
          'document_text': documentText,
        });
        return response.data as Map<String, dynamic>;
      });

  /// General-purpose RAG query across all previously-ingested documents.
  Future<Map<String, dynamic>> ragQuery(String question) => _guard(() async =>
      (await _dio.post('/query', data: {'question': question})).data as Map<String, dynamic>);

  Future<Map<String, dynamic>> compareDocuments(List<String> documentIds) => _guard(() async =>
      (await _dio.post('/intelligence/compare', data: {'document_ids': documentIds})).data
          as Map<String, dynamic>);

  // ===========================================================================
  // 6. Document Generation
  // ===========================================================================

  Future<Map<String, dynamic>> generateDocument({
    required String docType, // passport | license | birth | income | land
    required Map<String, dynamic> fields,
  }) =>
      _guard(() async {
        final response = await _dio.post('/generate/$docType', data: fields);
        return response.data as Map<String, dynamic>;
      });

  Future<Map<String, dynamic>> requestDocument({
    required String docType,
    required Map<String, dynamic> fields,
  }) =>
      _guard(() async {
        final response = await _dio.post('/generate/request/$docType', data: {
          'fields': fields,
        });
        return response.data as Map<String, dynamic>;
      });

  Future<Map<String, dynamic>> generationStatus(String requestId) => _guard(() async =>
      (await _dio.get('/generate/status/$requestId')).data as Map<String, dynamic>);

  Future<List<dynamic>> myGeneratedDocuments() =>
      _guard(() async => (await _dio.get('/generate/my')).data as List<dynamic>);

  Future<List<dynamic>> pendingGenerationRequests() =>
      _guard(() async => (await _dio.get('/generate/requests')).data as List<dynamic>);

  Future<void> approveGeneration(String requestId) =>
      _guard(() async => _dio.post('/generate/approve/$requestId'));

  Future<void> rejectGeneration(String requestId, {String? reason}) => _guard(
      () async => _dio.post('/generate/reject/$requestId', data: {'reason': reason}));

  Future<void> revokeDocument(String documentId, {String? reason}) => _guard(
      () async => _dio.post('/generate/revoke/$documentId', data: {'reason': reason}));

  Future<Map<String, dynamic>> verifyByDocumentNumber(String documentNumber) => _guard(() async =>
      (await _dio.get('/generate/verify/$documentNumber')).data as Map<String, dynamic>);

  Future<Map<String, dynamic>> generationTemplate(String docType) => _guard(() async =>
      (await _dio.get('/generate/template/$docType')).data as Map<String, dynamic>);

  String generatedDocumentDownloadUrl(String documentId) =>
      '${_dio.options.baseUrl}/generated/$documentId';

  // ===========================================================================
  // 7. Knowledge Graph
  // ===========================================================================

  Future<Map<String, dynamic>> graphForDocument(String documentId) => _guard(() async =>
      (await _dio.get('/graph/document/$documentId')).data as Map<String, dynamic>);

  Future<Map<String, dynamic>> graphForCitizen(String citizenId) => _guard(() async =>
      (await _dio.get('/graph/citizen/$citizenId')).data as Map<String, dynamic>);

  Future<Map<String, dynamic>> graphForCase(String caseId) => _guard(
      () async => (await _dio.get('/graph/case/$caseId')).data as Map<String, dynamic>);

  Future<Map<String, dynamic>> graphStats() =>
      _guard(() async => (await _dio.get('/graph/stats')).data as Map<String, dynamic>);

  Future<Map<String, dynamic>> graphExport() =>
      _guard(() async => (await _dio.get('/graph/export')).data as Map<String, dynamic>);

  Future<List<dynamic>> fraudClusters() =>
      _guard(() async => (await _dio.get('/graph/fraud-clusters')).data as List<dynamic>);

  Future<List<dynamic>> duplicateCitizens() =>
      _guard(() async => (await _dio.get('/graph/duplicates')).data as List<dynamic>);

  // ===========================================================================
  // 8. Tracking & Notifications
  // ===========================================================================

  Future<Map<String, dynamic>> trackApplication(String applicationId) => _guard(() async =>
      (await _dio.get('/tracking/$applicationId')).data as Map<String, dynamic>);

  Future<Map<String, dynamic>> trackByDocument(String documentId) => _guard(() async =>
      (await _dio.get('/tracking/document/$documentId')).data as Map<String, dynamic>);

  Future<List<dynamic>> notifications(String userId) => _guard(() async {
        final response = await _dio.get('/notifications', queryParameters: {'user_id': userId});
        final data = response.data;
        if (data is Map && data['notifications'] is List) return data['notifications'] as List;
        return data as List<dynamic>;
      });

  Future<void> markNotificationsRead(List<String> ids) =>
      _guard(() async => _dio.post('/notifications/mark-read', data: {'ids': ids}));

  Future<int> unreadNotificationCount(String userId) => _guard(() async {
        final response =
            await _dio.get('/notifications/count', queryParameters: {'user_id': userId});
        final data = response.data;
        if (data is Map) return (data['count'] as num?)?.toInt() ?? 0;
        return 0;
      });

  // ===========================================================================
  // 9. Security (Admin)
  // ===========================================================================

  Future<List<dynamic>> auditLog({int limit = 50}) => _guard(() async {
        final response = await _dio.get('/security/audit', queryParameters: {'limit': limit});
        final data = response.data;
        if (data is Map && data['entries'] is List) return data['entries'] as List;
        return data as List<dynamic>;
      });

  Future<Map<String, dynamic>> verifyAuditChain() => _guard(() async =>
      (await _dio.get('/security/audit/verify')).data as Map<String, dynamic>);

  Future<List<dynamic>> securityEvents() =>
      _guard(() async => (await _dio.get('/security/events')).data as List<dynamic>);

  Future<List<dynamic>> anomalies() =>
      _guard(() async => (await _dio.get('/security/anomalies')).data as List<dynamic>);

  // ===========================================================================
  // 10. Admin — user session management & department oversight
  // ===========================================================================

  Future<void> revokeUserSessions(String userId) => _guard(
      () async => _dio.post('/auth/admin/revoke-user', data: {'user_id': userId}));

  Future<Map<String, dynamic>> graphDepartments() => _guard(
      () async => (await _dio.get('/graph/departments')).data as Map<String, dynamic>);

  Future<List<dynamic>> allGeneratedDocuments() =>
      _guard(() async => (await _dio.get('/generate/list')).data as List<dynamic>);
}
