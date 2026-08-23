/// A government document issued through the generation engine (`/generate/*`).
class GeneratedDocumentModel {
  final String requestId;
  final String? documentId;
  final String documentType;
  final String status; // pending | approved | rejected | issued | revoked
  final String? documentNumber;
  final DateTime? issuedAt;
  final String? citizenName;
  final String? downloadUrl;

  GeneratedDocumentModel({
    required this.requestId,
    this.documentId,
    required this.documentType,
    this.status = 'pending',
    this.documentNumber,
    this.issuedAt,
    this.citizenName,
    this.downloadUrl,
  });

  factory GeneratedDocumentModel.fromJson(Map<String, dynamic> json) => GeneratedDocumentModel(
        requestId: (json['request_id'] ?? json['id'] ?? '').toString(),
        documentId: json['document_id']?.toString(),
        documentType: (json['document_type'] ?? json['doc_type'] ?? '').toString(),
        status: (json['status'] ?? 'pending').toString(),
        documentNumber: json['document_number']?.toString(),
        issuedAt: json['issued_at'] != null ? DateTime.tryParse(json['issued_at'].toString()) : null,
        citizenName: json['citizen_name']?.toString() ?? json['applicant_name']?.toString(),
        downloadUrl: json['download_url']?.toString(),
      );
}
