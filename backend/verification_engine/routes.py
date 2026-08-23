"""
verification_engine/routes.py — FastAPI endpoints for the Verification Engine.

Endpoints:
  POST /verify/document           — Run full 12-step verification on a document
  GET  /verify/status/{id}        — Get verification status and result
  POST /verify/manual-review      — Submit manual review outcome
  GET  /verify/history/{id}       — Get complete verification history
  GET  /verify/pending-reviews    — List pending manual reviews
  GET  /verify/departments        — List available department verifiers
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from verification_engine.database import VerificationDatabase
from verification_engine.models import (
    ManualReviewRequest,
    ReviewStatus,
    TrustBadge,
    VerificationHistoryEntry,
)
from verification_engine.pipeline import VerificationPipeline

logger = logging.getLogger(__name__)


# ── Pydantic request models ─────────────────────────────────────────────────

class VerifyDocumentRequest(BaseModel):
    document_id: str
    ocr_text: str = ""
    document_type: str = ""
    extracted_metadata: Dict[str, Any] = Field(default_factory=dict)
    file_hash: str = ""
    serial_number: str = ""
    qr_data: str = ""
    owner: str = ""


class ManualReviewSubmission(BaseModel):
    review_id: str
    badge: str = Field(..., description="green, yellow, or red")
    notes: str = ""
    reviewed_by: str = ""


# ── Router factory ───────────────────────────────────────────────────────────

def create_verification_router(
    pipeline: VerificationPipeline,
    db: VerificationDatabase,
) -> APIRouter:
    """Create and return the Verification Engine API router."""

    router = APIRouter(prefix="/verify", tags=["Verification Engine"])

    # ── POST /verify/document ────────────────────────────────────────────

    @router.post("/document", summary="Run full 12-step verification pipeline")
    async def verify_document(
        body: VerifyDocumentRequest,
        request: Request,
    ) -> Dict[str, Any]:
        """
        Run the full 12-step Government Verification Pipeline:

        1. Document Upload Validation
        2. OCR Quality Check
        3. AI Classification
        4. Serial Verification
        5. QR Verification
        6. Template Verification
        7. Issuing Authority Verification
        8. Government Registry Verification (department-specific)
        9. Ongoing Case Check
        10. Duplicate Check
        11. Fraud Score Calculation
        12. Trust Badge Assignment

        Returns verification result with trust badge (GREEN/YELLOW/RED).
        """
        if not body.document_id:
            raise HTTPException(400, "document_id is required")

        try:
            result = await pipeline.verify(
                document_id=body.document_id,
                ocr_text=body.ocr_text,
                extracted_metadata=body.extracted_metadata,
                document_type=body.document_type,
                file_hash=body.file_hash,
                serial_number=body.serial_number,
                qr_data=body.qr_data,
                owner=body.owner,
                officer="Automated Verification System",
                ip_address=request.client.host if request.client else "",
            )

            return {
                "status": "completed",
                "verification": result.to_dict(),
                "trust_badge": result.trust_badge.value,
                "fraud_score": round(result.fraud_score, 4),
                "summary": {
                    "total_steps": len(result.steps),
                    "passed": result.passed_count,
                    "failed": result.failed_count,
                    "warnings": result.warning_count,
                    "skipped": result.skipped_count,
                    "needs_manual_review": result.needs_manual_review,
                },
            }

        except Exception as e:
            logger.error("Verification failed for %s: %s", body.document_id, e, exc_info=True)
            raise HTTPException(500, f"Verification failed: {e}")

    # ── GET /verify/status/{id} ──────────────────────────────────────────

    @router.get("/status/{verification_id}", summary="Get verification status and result")
    async def get_verification_status(verification_id: str) -> Dict[str, Any]:
        """
        Get the status and detailed result of a verification run.

        Each step includes: confidence, evidence, timestamp, officer, verification_source.
        """
        result = await db.get_result(verification_id)
        if not result:
            raise HTTPException(404, "Verification result not found")

        return {
            "status": "found",
            "verification": result.to_dict(),
        }

    # ── POST /verify/manual-review ───────────────────────────────────────

    @router.post("/manual-review", summary="Submit manual review outcome")
    async def submit_manual_review(
        body: ManualReviewSubmission,
        request: Request,
    ) -> Dict[str, Any]:
        """
        Submit a manual review outcome for a YELLOW-flagged document.

        The reviewing officer assigns a final trust badge and notes.
        """
        review = await db.get_review(body.review_id)
        if not review:
            raise HTTPException(404, "Review request not found")
        if review.status != ReviewStatus.PENDING:
            raise HTTPException(409, f"Review already {review.status.value}")

        # Validate badge
        try:
            badge = TrustBadge(body.badge.lower())
        except ValueError:
            raise HTTPException(400, f"Invalid badge: {body.badge}. Must be green, yellow, or red")

        # Update review
        review.status = ReviewStatus.APPROVED
        review.reviewer_badge = badge
        review.reviewer_notes = body.notes
        review.reviewed_by = body.reviewed_by or "manual_reviewer"
        review.reviewed_at = datetime.now(timezone.utc)
        await db.save_review(review)

        # Log history
        await db.log_history(VerificationHistoryEntry(
            verification_id=review.verification_id,
            document_id=review.document_id,
            action="manual_review_completed",
            trust_badge=badge,
            confidence=1.0,
            evidence=f"Manual review by {review.reviewed_by}: badge={badge.value}, notes={body.notes}",
            officer=review.reviewed_by,
            verification_source="Manual Review",
        ))

        return {
            "status": "reviewed",
            "review_id": body.review_id,
            "final_badge": badge.value,
            "reviewed_by": review.reviewed_by,
        }

    # ── GET /verify/history/{id} ─────────────────────────────────────────

    @router.get("/history/{document_id}", summary="Get complete verification history")
    async def get_verification_history(
        document_id: str,
        limit: int = Query(100, ge=1, le=500),
    ) -> Dict[str, Any]:
        """
        Get complete verification history for a document.

        Includes all verification runs, step results, and manual reviews.
        Each entry includes: confidence, evidence, timestamp, officer, verification_source.
        """
        # All verification results for this document
        results = await db.get_results_for_document(document_id)

        # Complete history log
        history = await db.get_history(document_id, limit=limit)

        # Pending reviews
        all_reviews = await db.list_reviews()
        doc_reviews = [r for r in all_reviews if r.document_id == document_id]

        return {
            "document_id": document_id,
            "verification_count": len(results),
            "verifications": [r.to_dict() for r in results],
            "history": [h.to_dict() for h in history],
            "reviews": [r.to_dict() for r in doc_reviews],
            "latest_badge": results[0].trust_badge.value if results else None,
        }

    # ── GET /verify/pending-reviews ──────────────────────────────────────

    @router.get("/pending-reviews", summary="List pending manual reviews")
    async def list_pending_reviews(
        limit: int = Query(50, ge=1, le=200),
    ) -> Dict[str, Any]:
        """List all YELLOW-flagged documents awaiting manual review."""
        reviews = await db.list_reviews(status="pending", limit=limit)
        return {
            "pending_count": len(reviews),
            "reviews": [r.to_dict() for r in reviews],
        }

    # ── GET /verify/departments ──────────────────────────────────────────

    @router.get("/departments", summary="List available department verifiers")
    async def list_departments() -> Dict[str, Any]:
        """List all government departments with verification modules."""
        from verification_engine.departments import DepartmentType
        departments = [
            {
                "value": d.value,
                "display_name": d.value.replace("_", " ").title(),
                "description": _DEPT_DESCRIPTIONS.get(d.value, ""),
            }
            for d in DepartmentType
        ]
        return {"departments": departments}

    return router


# ── Department descriptions ─────────────────────────────────────────────────

_DEPT_DESCRIPTIONS = {
    "driving_school": "Verifies driving school registration, certificate number, and issuing authority",
    "education_board": "Verifies education certificates and board registrations (CBSE, ICSE, State Boards)",
    "revenue_department": "Verifies land records, survey numbers, and revenue documents",
    "rto": "Verifies driving licences, vehicle registrations via Sarathi/Vahan",
    "passport_office": "Verifies passport numbers against Passport Seva Portal",
    "registrar_office": "Verifies birth certificates and marriage certificates",
    "stamp_paper": "Verifies stamp paper serial numbers, issue dates, and treasury details",
    "general": "General document verification for unclassified documents",
}
