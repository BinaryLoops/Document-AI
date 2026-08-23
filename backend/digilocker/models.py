"""
digilocker/models.py — Domain models for the Government Digital Locker.

All metadata fields required by the spec:
  owner, department, document_type, case_type, serial_number, qr_code,
  upload_timestamp, verification_status, file_hash, encryption_ref,
  confidence_score.

Plus: version history, deletion requests, and audit records.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Document Categories ──────────────────────────────────────────────────────

class DocumentCategory(str, Enum):
    """Government document categories supported by the Digital Locker."""
    PASSPORT              = "passport"
    DRIVING_LICENCE       = "driving_licence"
    BIRTH_CERTIFICATE     = "birth_certificate"
    INCOME_CERTIFICATE    = "income_certificate"
    LAND_RECORD           = "land_record"
    EDUCATION_CERTIFICATE = "education_certificate"
    FIR                   = "fir"
    COURT_ORDER           = "court_order"
    OTHER                 = "other"


class VerificationStatus(str, Enum):
    """Verification state of a document."""
    PENDING   = "pending"
    VERIFIED  = "verified"
    REJECTED  = "rejected"
    EXPIRED   = "expired"


class DocumentLifecycle(str, Enum):
    """Lifecycle state — controls visibility and access."""
    PROCESSING      = "processing"
    ACTIVE          = "active"
    ARCHIVED        = "archived"
    DELETE_REQUESTED = "delete_requested"
    DELETED         = "deleted"       # soft-delete only — data stays in vault


class DeletionStatus(str, Enum):
    """Status of a deletion request."""
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ── Locker Document ─────────────────────────────────────────────────────────

@dataclass
class LockerDocument:
    """
    Primary document record in the Digital Locker.

    Every field listed in the specification is present:
      owner, department, document_type, case_type, serial_number,
      qr_code, upload_timestamp, verification_status, file_hash,
      encryption_ref, confidence_score.
    """

    # Identity
    document_id:    str = field(default_factory=lambda: str(uuid.uuid4()))
    owner:          str = ""           # user / citizen ID
    department:     str = ""           # issuing department

    # Classification
    document_type:  DocumentCategory = DocumentCategory.OTHER
    case_type:      str = ""           # e.g. "civil", "criminal", "administrative"
    serial_number:  str = ""           # government serial / reference number

    # QR & verification
    qr_code:            str = ""       # base64-encoded QR PNG
    verification_status: VerificationStatus = VerificationStatus.PENDING
    confidence_score:   float = 0.0    # OCR / classification confidence (0-1)

    # Integrity
    file_hash:      str = ""           # SHA-256 of original file bytes
    encryption_ref: str = ""           # vault path to encrypted blob

    # File metadata
    original_filename: str = ""
    file_size:         int = 0         # bytes
    mime_type:         str = ""
    page_count:        int = 0

    # Processing outputs
    ocr_text:           str = ""
    extracted_metadata: Dict[str, Any] = field(default_factory=dict)

    # Duplicate detection
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None  # document_id of original

    # Preview / thumbnail vault paths
    preview_ref:   str = ""
    thumbnail_ref: str = ""

    # Lifecycle
    lifecycle: DocumentLifecycle = DocumentLifecycle.PROCESSING
    version:   int = 1

    # Timestamps
    upload_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at:       datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a JSON-safe dictionary."""
        return {
            "document_id":        self.document_id,
            "owner":              self.owner,
            "department":         self.department,
            "document_type":      self.document_type.value,
            "case_type":          self.case_type,
            "serial_number":      self.serial_number,
            "qr_code":            self.qr_code,
            "verification_status": self.verification_status.value,
            "confidence_score":   round(self.confidence_score, 4),
            "file_hash":          self.file_hash,
            "encryption_ref":     self.encryption_ref,
            "original_filename":  self.original_filename,
            "file_size":          self.file_size,
            "mime_type":          self.mime_type,
            "page_count":         self.page_count,
            "is_duplicate":       self.is_duplicate,
            "duplicate_of":       self.duplicate_of,
            "lifecycle":          self.lifecycle.value,
            "version":            self.version,
            "upload_timestamp":   self.upload_timestamp.isoformat(),
            "updated_at":         self.updated_at.isoformat(),
            "extracted_metadata": self.extracted_metadata,
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """Public-facing dict — omits internal refs like encryption_ref."""
        d = self.to_dict()
        d.pop("encryption_ref", None)
        d.pop("ocr_text", None)
        return d


# ── Version History ──────────────────────────────────────────────────────────

@dataclass
class DocumentVersion:
    """
    Immutable version snapshot — INSERT only, never updated or deleted.
    Created every time a document is re-uploaded or modified.
    """
    version_id:   str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id:  str = ""
    version:      int = 1
    file_hash:    str = ""
    encryption_ref: str = ""
    file_size:    int = 0
    change_summary: str = ""
    created_by:   str = ""
    created_at:   datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version_id":     self.version_id,
            "document_id":    self.document_id,
            "version":        self.version,
            "file_hash":      self.file_hash,
            "file_size":      self.file_size,
            "change_summary": self.change_summary,
            "created_by":     self.created_by,
            "created_at":     self.created_at.isoformat(),
        }


# ── Deletion Request ────────────────────────────────────────────────────────

@dataclass
class DeletionRequest:
    """
    Tracks the controlled deletion workflow.
    Deletion must be requested and then approved by a system_admin.
    No permanent deletion is possible — approved requests soft-delete only.
    """
    request_id:   str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id:  str = ""
    requested_by: str = ""
    reason:       str = ""
    status:       DeletionStatus = DeletionStatus.PENDING
    approved_by:  Optional[str] = None
    reviewed_at:  Optional[datetime] = None
    created_at:   datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id":   self.request_id,
            "document_id":  self.document_id,
            "requested_by": self.requested_by,
            "reason":       self.reason,
            "status":       self.status.value,
            "approved_by":  self.approved_by,
            "reviewed_at":  self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at":   self.created_at.isoformat(),
        }


# ── Audit Log ────────────────────────────────────────────────────────────────

class AuditAction(str, Enum):
    UPLOAD           = "upload"
    VIEW             = "view"
    DOWNLOAD         = "download"
    SEARCH           = "search"
    ARCHIVE          = "archive"
    UNARCHIVE        = "unarchive"
    DELETE_REQUEST   = "delete_request"
    DELETE_APPROVE   = "delete_approve"
    DELETE_REJECT    = "delete_reject"
    VERIFY           = "verify"
    CLASSIFY         = "classify"


@dataclass
class AuditRecord:
    """Immutable audit trail entry — never updated or deleted."""
    audit_id:     str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id:  str = ""
    user_id:      str = ""
    action:       AuditAction = AuditAction.VIEW
    detail:       str = ""
    ip_address:   str = ""
    timestamp:    datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id":    self.audit_id,
            "document_id": self.document_id,
            "user_id":     self.user_id,
            "action":      self.action.value,
            "detail":      self.detail,
            "ip_address":  self.ip_address,
            "timestamp":   self.timestamp.isoformat(),
        }
