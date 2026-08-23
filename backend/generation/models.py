"""
generation/models.py — All domain models for the document generation engine.

Design: pure dataclasses, no ORM, JSON-serialisable via to_dict().
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class DocumentType(str, Enum):
    PASSPORT           = "passport"
    DRIVING_LICENSE    = "driving_license"
    BIRTH_CERTIFICATE  = "birth_certificate"
    INCOME_CERTIFICATE = "income_certificate"
    LAND_RECORD        = "land_record"


class GenerationStatus(str, Enum):
    PENDING    = "pending"     # request submitted, awaiting workflow
    VERIFYING  = "verifying"   # checking uploaded supporting docs
    CASE_CHECK = "case_check"  # checking for existing case / block
    APPROVED   = "approved"    # issuing authority approved
    GENERATING = "generating"  # PDF being built
    SIGNING    = "signing"     # digital signature being applied
    COMPLETE   = "complete"    # issued and downloadable
    REJECTED   = "rejected"    # rejected at any stage
    REVOKED    = "revoked"     # revoked post-issuance


class SignatureStatus(str, Enum):
    UNSIGNED  = "unsigned"
    SIGNED    = "signed"
    INVALID   = "invalid"      # signature verification failed


class WatermarkType(str, Enum):
    DRAFT    = "DRAFT"
    OFFICIAL = "OFFICIAL"
    REVOKED  = "REVOKED"
    SPECIMEN = "SPECIMEN"


# ─────────────────────────────────────────────────────────────────────────────
# Core domain models
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DocumentField:
    """A single filled-in template field."""
    name:        str
    label:       str
    value:       Any
    required:    bool = True
    section:     str  = "General"


@dataclass
class SupportingDocument:
    """Reference to an uploaded supporting document attached to the request."""
    doc_ref_id:   str
    doc_type:     str           # e.g. "Identity Proof", "Address Proof"
    filename:     str
    verified:     bool = False
    verified_by:  Optional[str] = None
    verified_at:  Optional[datetime] = None


@dataclass
class GenerationRequest:
    """
    A citizen's or official's request to generate an official document.

    Submitted via POST /generate/{doc_type}.
    """
    request_id:        str  = field(default_factory=lambda: str(uuid.uuid4()))
    document_type:     DocumentType = DocumentType.PASSPORT
    applicant_user_id: str  = ""          # the citizen this doc is for
    requested_by:      str  = ""          # user_id of the requester (usually same)
    issued_by:         Optional[str] = None  # issuing authority user_id
    department_code:   Optional[str] = None

    # Template fields as submitted
    fields:            Dict[str, Any] = field(default_factory=dict)

    # Supporting docs
    supporting_docs:   List[SupportingDocument] = field(default_factory=list)

    # Workflow state
    status:            GenerationStatus = GenerationStatus.PENDING
    rejection_reason:  Optional[str] = None
    case_clear:        bool = False
    verification_passed: bool = False

    # Timestamps
    submitted_at:  datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at:   Optional[datetime] = None
    completed_at:  Optional[datetime] = None
    updated_at:    datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id":          self.request_id,
            "document_type":       self.document_type.value,
            "applicant_user_id":   self.applicant_user_id,
            "requested_by":        self.requested_by,
            "issued_by":           self.issued_by,
            "department_code":     self.department_code,
            "fields":              self.fields,
            "supporting_docs":     [
                {
                    "doc_ref_id":  sd.doc_ref_id,
                    "doc_type":    sd.doc_type,
                    "filename":    sd.filename,
                    "verified":    sd.verified,
                    "verified_by": sd.verified_by,
                    "verified_at": sd.verified_at.isoformat() if sd.verified_at else None,
                }
                for sd in self.supporting_docs
            ],
            "status":              self.status.value,
            "rejection_reason":    self.rejection_reason,
            "case_clear":          self.case_clear,
            "verification_passed": self.verification_passed,
            "submitted_at":        self.submitted_at.isoformat(),
            "approved_at":         self.approved_at.isoformat() if self.approved_at else None,
            "completed_at":        self.completed_at.isoformat() if self.completed_at else None,
            "updated_at":          self.updated_at.isoformat(),
        }


@dataclass
class GeneratedDocument:
    """
    An officially issued government document — fully generated and signed.

    Stored after the workflow reaches COMPLETE status.
    """
    doc_id:          str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id:      str = ""
    document_type:   DocumentType = DocumentType.PASSPORT
    document_number: str = ""       # official document number e.g. "IND-PP-2026-000001"

    # Applicant info (denormalised for fast lookup)
    applicant_user_id: str = ""
    applicant_name:    str = ""

    # Issuance
    issued_by:         str = ""     # issuing authority user_id
    department_code:   str = ""
    issued_at:         datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    valid_from:        Optional[datetime] = None
    valid_until:       Optional[datetime] = None

    # Digital signature
    signature_status:  SignatureStatus = SignatureStatus.UNSIGNED
    signature_hash:    str = ""     # hex SHA-256 of PDF bytes
    signature_value:   str = ""     # base64 RSA signature
    signed_by:         Optional[str] = None
    signed_at:         Optional[datetime] = None

    # QR code
    qr_verification_url: str = ""
    qr_payload_hash:     str = ""   # SHA-256 of QR JSON payload

    # Watermark
    watermark_type:    WatermarkType = WatermarkType.OFFICIAL

    # PDF storage
    pdf_path:          str = ""     # filesystem path relative to storage root
    pdf_size_bytes:    int = 0

    # Status
    status:            GenerationStatus = GenerationStatus.COMPLETE
    revoked:           bool = False
    revoked_at:        Optional[datetime] = None
    revoked_by:        Optional[str] = None
    revoke_reason:     Optional[str] = None

    # Filled fields snapshot
    fields:            Dict[str, Any] = field(default_factory=dict)

    created_at:  datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_id":              self.doc_id,
            "request_id":         self.request_id,
            "document_type":      self.document_type.value,
            "document_number":    self.document_number,
            "applicant_user_id":  self.applicant_user_id,
            "applicant_name":     self.applicant_name,
            "issued_by":          self.issued_by,
            "department_code":    self.department_code,
            "issued_at":          self.issued_at.isoformat(),
            "valid_from":         self.valid_from.isoformat() if self.valid_from else None,
            "valid_until":        self.valid_until.isoformat() if self.valid_until else None,
            "signature_status":   self.signature_status.value,
            "signature_hash":     self.signature_hash,
            "signed_by":          self.signed_by,
            "signed_at":          self.signed_at.isoformat() if self.signed_at else None,
            "qr_verification_url": self.qr_verification_url,
            "watermark_type":     self.watermark_type.value,
            "pdf_size_bytes":     self.pdf_size_bytes,
            "status":             self.status.value,
            "revoked":            self.revoked,
            "revoked_at":         self.revoked_at.isoformat() if self.revoked_at else None,
            "revoke_reason":      self.revoke_reason,
            "fields":             self.fields,
            "created_at":         self.created_at.isoformat(),
        }

    def to_public_dict(self) -> Dict[str, Any]:
        """Safe public view — excludes internal paths and raw signature bytes."""
        d = self.to_dict()
        d.pop("pdf_path", None)
        d.pop("signature_value", None)
        d.pop("qr_payload_hash", None)
        return d


@dataclass
class GenerationAuditEvent:
    """Immutable audit trail for every workflow step."""
    event_id:      str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id:    str = ""
    doc_id:        Optional[str] = None
    actor_user_id: str = ""
    action:        str = ""          # e.g. "submitted", "approved", "signed"
    detail:        Optional[str] = None
    ip_address:    str = ""
    timestamp:     datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id":      self.event_id,
            "request_id":    self.request_id,
            "doc_id":        self.doc_id,
            "actor_user_id": self.actor_user_id,
            "action":        self.action,
            "detail":        self.detail,
            "ip_address":    self.ip_address,
            "timestamp":     self.timestamp.isoformat(),
        }
