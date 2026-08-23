"""
tracking/models.py -- Data models for Tracking & Notification system.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Tracking Stages ─────────────────────────────────────────────────────────

class TrackingStage(str, Enum):
    """Ordered lifecycle stages for a government document application."""
    SUBMITTED           = "submitted"
    VERIFICATION        = "verification"
    OFFICER_REVIEW      = "officer_review"
    ISSUING_AUTHORITY   = "issuing_authority"
    GENERATED           = "generated"
    PRINTED             = "printed"
    DISPATCHED          = "dispatched"
    DELIVERED           = "delivered"
    REJECTED            = "rejected"
    ON_HOLD             = "on_hold"

    @classmethod
    def ordered(cls) -> List["TrackingStage"]:
        """Return the happy-path stage order."""
        return [
            cls.SUBMITTED, cls.VERIFICATION, cls.OFFICER_REVIEW,
            cls.ISSUING_AUTHORITY, cls.GENERATED, cls.PRINTED,
            cls.DISPATCHED, cls.DELIVERED,
        ]

    @classmethod
    def index(cls, stage: "TrackingStage") -> int:
        """Return the zero-based index of a stage (for progress %)."""
        ordered = cls.ordered()
        try:
            return ordered.index(stage)
        except ValueError:
            return -1


# ── Notification Types ──────────────────────────────────────────────────────

class NotificationType(str, Enum):
    UPLOAD_SUCCESSFUL       = "upload_successful"
    VERIFICATION_COMPLETE   = "verification_complete"
    MANUAL_REVIEW           = "manual_review"
    DOCUMENT_APPROVED       = "document_approved"
    DOCUMENT_GENERATED      = "generated"
    DISPATCHED              = "dispatched"
    DELIVERED               = "delivered"
    SUSPICIOUS_LOGIN        = "suspicious_login"
    DOCUMENT_REJECTED       = "document_rejected"
    STATUS_UPDATE           = "status_update"


# Notification type → human-readable message template
NOTIFICATION_TEMPLATES: Dict[NotificationType, str] = {
    NotificationType.UPLOAD_SUCCESSFUL:     "Your document '{doc_name}' has been uploaded successfully.",
    NotificationType.VERIFICATION_COMPLETE: "Verification is complete for '{doc_name}'.",
    NotificationType.MANUAL_REVIEW:         "Your document '{doc_name}' requires manual review by an officer.",
    NotificationType.DOCUMENT_APPROVED:     "Your document '{doc_name}' has been approved by the issuing authority.",
    NotificationType.DOCUMENT_GENERATED:    "Your official document '{doc_name}' has been generated and is ready.",
    NotificationType.DISPATCHED:            "Your document '{doc_name}' has been dispatched for delivery.",
    NotificationType.DELIVERED:             "Your document '{doc_name}' has been delivered.",
    NotificationType.SUSPICIOUS_LOGIN:      "A suspicious login was detected on your account from {location}.",
    NotificationType.DOCUMENT_REJECTED:     "Your document '{doc_name}' has been rejected. Reason: {reason}.",
    NotificationType.STATUS_UPDATE:         "Status update for '{doc_name}': {status}.",
}


# ── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class TrackingEvent:
    """A single stage transition event in the tracking history."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stage: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    officer_id: str = ""
    officer_name: str = ""
    department: str = ""
    notes: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "stage": self.stage,
            "timestamp": self.timestamp,
            "officer_id": self.officer_id,
            "officer_name": self.officer_name,
            "department": self.department,
            "notes": self.notes,
            "metadata": self.metadata,
        }


@dataclass
class TrackingRecord:
    """Full tracking record for a document application."""
    application_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    document_type: str = ""
    document_name: str = ""
    applicant_id: str = ""
    applicant_name: str = ""
    current_stage: str = TrackingStage.SUBMITTED.value
    department: str = ""
    assigned_officer: str = ""
    assigned_officer_name: str = ""
    eta: str = ""                    # ISO datetime
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    history: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        total = len(TrackingStage.ordered())
        current_idx = TrackingStage.index(TrackingStage(self.current_stage)) if self.current_stage in [s.value for s in TrackingStage] else -1
        progress = round((current_idx / max(total - 1, 1)) * 100, 1) if current_idx >= 0 else 0

        return {
            "application_id": self.application_id,
            "document_id": self.document_id,
            "document_type": self.document_type,
            "document_name": self.document_name,
            "applicant_id": self.applicant_id,
            "applicant_name": self.applicant_name,
            "current_stage": self.current_stage,
            "progress_percent": progress,
            "department": self.department,
            "assigned_officer": self.assigned_officer,
            "assigned_officer_name": self.assigned_officer_name,
            "eta": self.eta,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "history": self.history,
            "stages": [
                {
                    "stage": s.value,
                    "label": s.value.replace("_", " ").title(),
                    "completed": TrackingStage.index(s) <= current_idx,
                    "current": s.value == self.current_stage,
                }
                for s in TrackingStage.ordered()
            ],
        }


@dataclass
class Notification:
    """A user notification."""
    notification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    notification_type: str = ""
    title: str = ""
    message: str = ""
    is_read: bool = False
    application_id: str = ""
    document_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "type": self.notification_type,
            "title": self.title,
            "message": self.message,
            "is_read": self.is_read,
            "application_id": self.application_id,
            "document_id": self.document_id,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
