import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/constants.dart';

/// Wraps secure (token) and non-secure (preferences) local storage behind
/// one simple API. Tokens are never kept in plain SharedPreferences.
class StorageService {
  StorageService._internal();
  static final StorageService instance = StorageService._internal();

  final FlutterSecureStorage _secure = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  SharedPreferences? _prefs;

  Future<SharedPreferences> get _preferences async {
    _prefs ??= await SharedPreferences.getInstance();
    return _prefs!;
  }

  // ---- Tokens ----
  Future<void> saveTokens({
    required String accessToken,
    String? refreshToken,
  }) async {
    await _secure.write(key: AppConstants.keyAccessToken, value: accessToken);
    if (refreshToken != null) {
      await _secure.write(
        key: AppConstants.keyRefreshToken,
        value: refreshToken,
      );
    }
  }

  Future<String?> getAccessToken() =>
      _secure.read(key: AppConstants.keyAccessToken);
  Future<String?> getRefreshToken() =>
      _secure.read(key: AppConstants.keyRefreshToken);

  Future<void> clearTokens() async {
    await _secure.delete(key: AppConstants.keyAccessToken);
    await _secure.delete(key: AppConstants.keyRefreshToken);
  }

  // ---- User profile / role (cached for quick UI decisions) ----
  Future<void> saveUserProfile(Map<String, dynamic> profile) async {
    final prefs = await _preferences;
    await prefs.setString(AppConstants.keyUserProfile, jsonEncode(profile));
  }

  Future<Map<String, dynamic>?> getUserProfile() async {
    final prefs = await _preferences;
    final raw = prefs.getString(AppConstants.keyUserProfile);
    if (raw == null) return null;
    return jsonDecode(raw) as Map<String, dynamic>;
  }

  Future<void> saveRole(String role) async {
    final prefs = await _preferences;
    await prefs.setString(AppConstants.keyUserRole, role);
  }

  Future<String?> getRole() async {
    final prefs = await _preferences;
    return prefs.getString(AppConstants.keyUserRole);
  }

  Future<void> clearSession() async {
    await clearTokens();
    final prefs = await _preferences;
    await prefs.remove(AppConstants.keyUserProfile);
    await prefs.remove(AppConstants.keyUserRole);
  }

  // ---- Theme preference ----
  Future<void> saveThemeMode(String mode) async {
    final prefs = await _preferences;
    await prefs.setString(AppConstants.keyThemeMode, mode);
  }

  Future<String?> getThemeMode() async {
    final prefs = await _preferences;
    return prefs.getString(AppConstants.keyThemeMode);
  }

  Future<void> saveLocalDocument(Map<String, dynamic> document) async {
    final prefs = await _preferences;
    final documents = await getLocalDocuments();
    documents.removeWhere(
      (item) => item['document_id'] == document['document_id'],
    );
    documents.insert(0, document);
    await prefs.setString(
      AppConstants.keyLocalDocuments,
      jsonEncode(documents.take(100).toList()),
    );
  }

  Future<List<Map<String, dynamic>>> getLocalDocuments() async {
    final prefs = await _preferences;
    final raw = prefs.getString(AppConstants.keyLocalDocuments);
    if (raw == null) return [];
    final decoded = jsonDecode(raw) as List?;
    return decoded
            ?.whereType<Map>()
            .map((item) => Map<String, dynamic>.from(item))
            .toList() ??
        [];
  }
}
