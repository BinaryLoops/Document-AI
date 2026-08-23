import 'package:dio/dio.dart';
import 'package:logger/logger.dart';

import '../core/constants.dart';
import 'storage_service.dart';

/// Thin exception type surfaced to the UI layer so screens can show a
/// friendly, consistent error message regardless of the underlying cause.
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic data;

  ApiException(this.message, {this.statusCode, this.data});

  @override
  String toString() => message;
}

/// Centralised Dio instance shared by [ApiService].
///
/// Responsibilities:
///  - attach the bearer token to every request
///  - retry idempotent GET requests once on transient network failure
///  - transparently refresh the access token on a 401 and replay the request
///  - normalise all failures into [ApiException]
class ApiClient {
  ApiClient._internal() {
    _dio = Dio(
      BaseOptions(
        baseUrl: AppConstants.apiBaseUrl,
        connectTimeout: AppConstants.apiConnectTimeout,
        receiveTimeout: AppConstants.apiReceiveTimeout,
        headers: {'Accept': 'application/json'},
      ),
    );

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await StorageService.instance.getAccessToken();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (DioException error, handler) async {
          // Attempt a single silent token refresh on 401, then replay once.
          if (error.response?.statusCode == 401 &&
              error.requestOptions.extra['retried'] != true) {
            final refreshed = await _tryRefreshToken();
            if (refreshed) {
              final opts = error.requestOptions;
              opts.extra['retried'] = true;
              final token = await StorageService.instance.getAccessToken();
              opts.headers['Authorization'] = 'Bearer $token';
              try {
                final response = await _dio.fetch(opts);
                return handler.resolve(response);
              } catch (_) {
                // fall through to normal error handling
              }
            }
          }

          // One transient retry for network-level failures on GET requests.
          final isNetworkError = error.type == DioExceptionType.connectionError ||
              error.type == DioExceptionType.connectionTimeout ||
              error.type == DioExceptionType.receiveTimeout;
          if (isNetworkError &&
              error.requestOptions.method == 'GET' &&
              error.requestOptions.extra['networkRetried'] != true) {
            error.requestOptions.extra['networkRetried'] = true;
            try {
              final response = await _dio.fetch(error.requestOptions);
              return handler.resolve(response);
            } catch (_) {
              // fall through
            }
          }

          handler.next(error);
        },
      ),
    );

    if (const bool.fromEnvironment('dart.vm.product') == false) {
      _dio.interceptors.add(
        LogInterceptor(
          requestBody: false,
          responseBody: false,
          logPrint: (obj) => _logger.d(obj.toString()),
        ),
      );
    }
  }

  static final ApiClient instance = ApiClient._internal();
  static final Logger _logger = Logger(printer: PrettyPrinter(methodCount: 0));

  late final Dio _dio;
  Dio get dio => _dio;

  bool _refreshing = false;

  Future<bool> _tryRefreshToken() async {
    if (_refreshing) return false;
    _refreshing = true;
    try {
      final refreshToken = await StorageService.instance.getRefreshToken();
      if (refreshToken == null) return false;
      final response = await Dio(BaseOptions(baseUrl: AppConstants.apiBaseUrl)).post(
        '/auth/refresh',
        data: {'refresh_token': refreshToken},
      );
      final data = response.data as Map<String, dynamic>;
      final access = data['access_token'] as String?;
      final newRefresh = data['refresh_token'] as String?;
      if (access == null) return false;
      await StorageService.instance.saveTokens(accessToken: access, refreshToken: newRefresh);
      return true;
    } catch (_) {
      return false;
    } finally {
      _refreshing = false;
    }
  }

  /// Converts any error thrown by Dio into an [ApiException] with a
  /// user-friendly message extracted from the backend's error envelope.
  static ApiException normalize(Object error) {
    if (error is DioException) {
      final response = error.response;
      String message = 'Something went wrong. Please try again.';

      if (response?.data is Map) {
        final data = response!.data as Map;
        if (data['message'] is String) {
          message = data['message'] as String;
        } else if (data['detail'] is String) {
          message = data['detail'] as String;
        } else if (data['detail'] is List && (data['detail'] as List).isNotEmpty) {
          final first = (data['detail'] as List).first;
          if (first is Map && first['msg'] != null) {
            message = first['msg'].toString();
          }
        }
      } else {
        switch (error.type) {
          case DioExceptionType.connectionTimeout:
          case DioExceptionType.sendTimeout:
          case DioExceptionType.receiveTimeout:
            message = 'The server took too long to respond. Please try again.';
            break;
          case DioExceptionType.connectionError:
            message = 'No internet connection. This action has been queued.';
            break;
          default:
            message = error.message ?? message;
        }
      }
      return ApiException(message, statusCode: response?.statusCode, data: response?.data);
    }
    return ApiException(error.toString());
  }
}
