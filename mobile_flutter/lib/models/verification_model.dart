import '../core/constants.dart';

/// Result of the 12-step government verification pipeline (`/verify/*`).
class VerificationResult {
  final String verificationId;
  final String documentId;
  final TrustBadge trustBadge;
  final double fraudScore;
  final String status; // pending | verified | flagged | rejected
  final List<VerificationStep> steps;
  final String? message;
  final DateTime? verifiedAt;

  VerificationResult({
    required this.verificationId,
    required this.documentId,
    required this.trustBadge,
    this.fraudScore = 0.0,
    this.status = 'pending',
    this.steps = const [],
    this.message,
    this.verifiedAt,
  });

  factory VerificationResult.fromJson(Map<String, dynamic> json) {
    return VerificationResult(
      verificationId: (json['verification_id'] ?? json['id'] ?? '').toString(),
      documentId: (json['document_id'] ?? '').toString(),
      trustBadge: TrustBadgeX.fromString(
        (json['trust_badge'] ?? json['badge'])?.toString(),
      ),
      fraudScore: (json['fraud_score'] as num?)?.toDouble() ?? 0.0,
      status: (json['status'] ?? 'pending').toString(),
      steps: (json['steps'] as List?)
              ?.map((e) => VerificationStep.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      message: json['message']?.toString(),
      verifiedAt:
          json['verified_at'] != null ? DateTime.tryParse(json['verified_at'].toString()) : null,
    );
  }
}

class VerificationStep {
  final String name;
  final bool passed;
  final String? detail;

  VerificationStep({required this.name, required this.passed, this.detail});

  factory VerificationStep.fromJson(Map<String, dynamic> json) => VerificationStep(
        name: (json['name'] ?? json['step'] ?? '').toString(),
        passed: json['passed'] == true || json['status'] == 'passed',
        detail: json['detail']?.toString(),
      );
}
