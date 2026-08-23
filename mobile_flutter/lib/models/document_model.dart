import '../core/constants.dart';

/// A document stored in the citizen's Digital Locker (`/documents/*`).
class DocumentModel {
  final String id;
  final String filename;
  final String? category;
  final String status; // uploaded | processing | verified | rejected | archived
  final TrustBadge trustBadge;
  final double? classificationConfidence;
  final DateTime? uploadedAt;
  final String? ownerId;
  final List<ExtractedField> extractedFields;
  final String? thumbnailUrl;

  DocumentModel({
    required this.id,
    required this.filename,
    this.category,
    this.status = 'uploaded',
    this.trustBadge = TrustBadge.unknown,
    this.classificationConfidence,
    this.uploadedAt,
    this.ownerId,
    this.extractedFields = const [],
    this.thumbnailUrl,
  });

  factory DocumentModel.fromJson(Map<String, dynamic> json) {
    return DocumentModel(
      id: (json['document_id'] ?? json['id'] ?? '').toString(),
      filename: (json['filename'] ?? json['file_name'] ?? 'Document').toString(),
      category: json['category']?.toString() ?? json['document_type']?.toString(),
      status: (json['status'] ?? 'uploaded').toString(),
      trustBadge: TrustBadgeX.fromString(json['trust_badge']?.toString()),
      classificationConfidence: (json['classification_confidence'] as num?)?.toDouble(),
      uploadedAt: json['uploaded_at'] != null
          ? DateTime.tryParse(json['uploaded_at'].toString())
          : (json['created_at'] != null ? DateTime.tryParse(json['created_at'].toString()) : null),
      ownerId: json['owner_id']?.toString() ?? json['owner']?.toString(),
      extractedFields: (json['extracted_fields'] as List?)
              ?.map((e) => ExtractedField.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      thumbnailUrl: json['thumbnail_url']?.toString(),
    );
  }
}

class ExtractedField {
  final String field;
  final String? value;
  final double confidence;
  final String? evidenceSnippet;

  ExtractedField({
    required this.field,
    this.value,
    this.confidence = 0.0,
    this.evidenceSnippet,
  });

  factory ExtractedField.fromJson(Map<String, dynamic> json) => ExtractedField(
        field: (json['field'] ?? '').toString(),
        value: json['value']?.toString(),
        confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
        evidenceSnippet: (json['evidence'] is Map)
            ? (json['evidence']['evidence_snippet']?.toString())
            : json['evidence_snippet']?.toString(),
      );
}
