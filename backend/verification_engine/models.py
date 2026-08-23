"""
verification_engine/models.py — Domain models for the Verification Engine.

Covers:
  - TrustBadge (GREEN / YELLOW / RED)
  - VerificationStep — one step in the pipeline
  - VerificationResult — aggregated result of all steps
  - ManualReviewRequest — for YELLOW-flagged documents
  - VerificationHistory — immutable audit trail
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Trust Badge ──────────────────────────────────────────────────────────────

class TrustBadge(str, Enum):
    """Final verification outcome."""
    GREEN  = "green"    # Fully verified
    YELLOW = "yellow"   # Needs manual review
    RED    = "red"      # Verification failed


class VerificationStepStatus(str, Enum):
    """Status of an individual verification step."""
    PASSED  = "passed"
    FAILED  = "failed"
    SKIPPED = "skipped"
    PENDING = "pending"
    WARNING = "warning"   # passed with caveats


class ReviewStatus(str, Enum):
    PENDING   = "pending"
    APPROVED  = "approved"
    REJECTED  = "rejected"


class DepartmentType(str, Enum):
    """Government departments with verification modules."""
    DRIVING_SCHOOL     = "driving_school"
    EDUCATION_BOARD    = "education_board"
    REVENUE_DEPARTMENT = "revenue_department"
    RTO                = "rto"
    PASSPORT_OFFICE    = "passport_office"
    REGISTRAR_OFFICE   = "registrar_office"
    STAMP_PAPER        = "stamp_paper"
    GENERAL            = "general"


# ── Verification Step ────────────────────────────────────────────────────────

@dataclass
class VerificationStep:
    """
    One step in the verification pipeline.

    Every step includes the five required fields:
      confidence, evidence, timestamp, officer, verification_source
    """
    step_id:    str = field(default_factory=lambda: str(uuid.uuid4()))
    step_name:  str = ""
    step_order: int = 0
    status:     VerificationStepStatus = VerificationStepStatus.PENDING

    # Required fields per spec
    confidence:          float = 0.0     # 0.0 – 1.0
    evidence:            str   = ""      # description of what was checked
    timestamp:           datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    officer:             str   = ""      # verifying officer / system name
    verification_source: str   = ""      # e.g. "Government Registry API", "QR decode"

    # Additional detail
    detail:     Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0   # how long this step took

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id":             self.step_id,
            "step_name":           self.step_name,
            "step_order":          self.step_order,
            "status":              self.status.value,
            "confidence":          round(self.confidence, 4),
            "evidence":            self.evidence,
            "timestamp":           self.timestamp.isoformat(),
            "officer":             self.officer,
            "verification_source": self.verification_source,
            "detail":              self.detail,
            "duration_ms":         self.duration_ms,
        }


# ── Verification Result ─────────────────────────────────────────────────────

@dataclass
class VerificationResult:
    """
    Aggregated result of all verification steps for a document.
    """
    verification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id:     str = ""
    trust_badge:     TrustBadge = TrustBadge.YELLOW
    fraud_score:     float = 0.0     # 0.0 (clean) – 1.0 (fraudulent)
    overall_confidence: float = 0.0

    steps:           List[VerificationStep] = field(default_factory=list)
    department:      DepartmentType = DepartmentType.GENERAL

    # Summary
    passed_count: int = 0
    failed_count: int = 0
    warning_count: int = 0
    skipped_count: int = 0

    # Timestamps
    started_at:   datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    # Manual review
    needs_manual_review: bool = False
    review_reason:       str  = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id":    self.verification_id,
            "document_id":        self.document_id,
            "trust_badge":        self.trust_badge.value,
            "fraud_score":        round(self.fraud_score, 4),
            "overall_confidence": round(self.overall_confidence, 4),
            "steps":              [s.to_dict() for s in self.steps],
            "department":         self.department.value,
            "passed_count":       self.passed_count,
            "failed_count":       self.failed_count,
            "warning_count":      self.warning_count,
            "skipped_count":      self.skipped_count,
            "started_at":         self.started_at.isoformat(),
            "completed_at":       self.completed_at.isoformat() if self.completed_at else None,
            "needs_manual_review": self.needs_manual_review,
            "review_reason":      self.review_reason,
        }


# ── Manual Review ────────────────────────────────────────────────────────────

@dataclass
class ManualReviewRequest:
    """A request for human officer to manually review a document."""
    review_id:       str = field(default_factory=lambda: str(uuid.uuid4()))
    verification_id: str = ""
    document_id:     str = ""
    reason:          str = ""
    status:          ReviewStatus = ReviewStatus.PENDING
    assigned_to:     str = ""

    # Review outcome
    reviewer_notes:  str = ""
    reviewer_badge:  Optional[TrustBadge] = None
    reviewed_by:     str = ""
    reviewed_at:     Optional[datetime] = None

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id":       self.review_id,
            "verification_id": self.verification_id,
            "document_id":     self.document_id,
            "reason":          self.reason,
            "status":          self.status.value,
            "assigned_to":     self.assigned_to,
            "reviewer_notes":  self.reviewer_notes,
            "reviewer_badge":  self.reviewer_badge.value if self.reviewer_badge else None,
            "reviewed_by":     self.reviewed_by,
            "reviewed_at":     self.reviewed_at.isoformat() if self.reviewed_at else None,
            "created_at":      self.created_at.isoformat(),
        }


# ── Verification History ────────────────────────────────────────────────────

@dataclass
class VerificationHistoryEntry:
    """Immutable audit record — one per verification run or review action."""
    entry_id:        str = field(default_factory=lambda: str(uuid.uuid4()))
    verification_id: str = ""
    document_id:     str = ""
    action:          str = ""     # "verification_started", "step_completed", "review_submitted"
    trust_badge:     Optional[TrustBadge] = None
    confidence:      float = 0.0
    evidence:        str   = ""
    officer:         str   = ""
    verification_source: str = ""
    detail:          Dict[str, Any] = field(default_factory=dict)
    timestamp:       datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id":            self.entry_id,
            "verification_id":    self.verification_id,
            "document_id":        self.document_id,
            "action":             self.action,
            "trust_badge":        self.trust_badge.value if self.trust_badge else None,
            "confidence":         round(self.confidence, 4),
            "evidence":           self.evidence,
            "officer":            self.officer,
            "verification_source": self.verification_source,
            "detail":             self.detail,
            "timestamp":          self.timestamp.isoformat(),
        }
