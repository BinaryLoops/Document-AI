class NotificationModel {
  final String id;
  final String title;
  final String message;
  final bool read;
  final DateTime createdAt;
  final String? type;

  NotificationModel({
    required this.id,
    required this.title,
    required this.message,
    this.read = false,
    required this.createdAt,
    this.type,
  });

  factory NotificationModel.fromJson(Map<String, dynamic> json) => NotificationModel(
        id: (json['id'] ?? json['notification_id'] ?? '').toString(),
        title: (json['title'] ?? 'Notification').toString(),
        message: (json['message'] ?? json['body'] ?? '').toString(),
        read: json['read'] == true,
        createdAt: DateTime.tryParse(json['created_at']?.toString() ?? '') ?? DateTime.now(),
        type: json['type']?.toString(),
      );
}

/// Application/document tracking record (`/tracking/*`).
class TrackingModel {
  final String applicationId;
  final String stage; // e.g. submitted, under_review, approved, dispatched, delivered
  final List<TrackingEvent> history;
  final DateTime? updatedAt;

  TrackingModel({
    required this.applicationId,
    required this.stage,
    this.history = const [],
    this.updatedAt,
  });

  factory TrackingModel.fromJson(Map<String, dynamic> json) => TrackingModel(
        applicationId: (json['application_id'] ?? json['id'] ?? '').toString(),
        stage: (json['stage'] ?? json['status'] ?? 'submitted').toString(),
        history: (json['history'] as List?)
                ?.map((e) => TrackingEvent.fromJson(e as Map<String, dynamic>))
                .toList() ??
            const [],
        updatedAt:
            json['updated_at'] != null ? DateTime.tryParse(json['updated_at'].toString()) : null,
      );
}

class TrackingEvent {
  final String stage;
  final DateTime timestamp;
  final String? note;

  TrackingEvent({required this.stage, required this.timestamp, this.note});

  factory TrackingEvent.fromJson(Map<String, dynamic> json) => TrackingEvent(
        stage: (json['stage'] ?? '').toString(),
        timestamp: DateTime.tryParse(json['timestamp']?.toString() ?? '') ?? DateTime.now(),
        note: json['note']?.toString(),
      );
}
