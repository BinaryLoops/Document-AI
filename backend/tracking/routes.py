"""
tracking/routes.py -- FastAPI endpoints for Tracking & Notifications.

Endpoints:
  GET  /tracking/{id}           — Get application tracking status
  GET  /tracking/document/{id}  — Get tracking by document ID
  POST /tracking/create         — Create a new tracking record
  POST /tracking/update/{id}    — Update tracking stage
  GET  /notifications           — Get user notifications
  POST /notifications/mark-read — Mark notifications as read
  GET  /notifications/count     — Get unread notification count
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from tracking.models import TrackingStage, NotificationType
from tracking import database as db

logger = logging.getLogger(__name__)


# ── Request models ───────────────────────────────────────────────────────────

class CreateTrackingRequest(BaseModel):
    document_id: str = Field("", description="Document ID")
    document_type: str = Field("", description="Document type (passport, fir, etc.)")
    document_name: str = Field("", description="Document display name")
    applicant_id: str = Field(..., description="Applicant user ID")
    applicant_name: str = Field("", description="Applicant name")
    department: str = Field("", description="Processing department")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class UpdateStageRequest(BaseModel):
    stage: str = Field(..., description="New stage (submitted, verification, officer_review, etc.)")
    officer_id: str = Field("", description="Officer ID performing the action")
    officer_name: str = Field("", description="Officer name")
    department: str = Field("", description="Department")
    notes: str = Field("", description="Notes about this stage transition")


class MarkReadRequest(BaseModel):
    notification_ids: Optional[List[str]] = Field(
        None,
        description="Specific notification IDs to mark as read. If omitted, marks ALL as read.",
    )
    user_id: str = Field(..., description="User ID")


# ── Router factory ───────────────────────────────────────────────────────────

def create_tracking_router() -> tuple:
    """Create and return tracking and notification routers."""

    tracking_router = APIRouter(prefix="/tracking", tags=["Tracking"])
    notif_router = APIRouter(prefix="/notifications", tags=["Notifications"])

    # ── GET /tracking/{id} ───────────────────────────────────────────────

    @tracking_router.get(
        "/{application_id}",
        summary="Get application tracking status",
    )
    async def get_tracking(application_id: str) -> Dict[str, Any]:
        """
        Get the full tracking status of a document application.

        Returns:
        - Current stage and progress percentage
        - Stage timeline (all stages with completed/current markers)
        - Assigned officer and department
        - ETA for delivery
        - Full delivery history (audit trail)
        """
        record = await db.get_tracking_record(application_id)
        if not record:
            raise HTTPException(404, f"Tracking record not found: {application_id}")

        return {
            "status": "success",
            "tracking": record.to_dict(),
        }

    # ── GET /tracking/document/{id} ──────────────────────────────────────

    @tracking_router.get(
        "/document/{document_id}",
        summary="Get tracking by document ID",
    )
    async def get_tracking_by_doc(document_id: str) -> Dict[str, Any]:
        """Get tracking status by document ID."""
        record = await db.get_tracking_by_document(document_id)
        if not record:
            raise HTTPException(404, f"No tracking record for document: {document_id}")

        return {
            "status": "success",
            "tracking": record.to_dict(),
        }

    # ── POST /tracking/create ────────────────────────────────────────────

    @tracking_router.post(
        "/create",
        summary="Create a new tracking record",
    )
    async def create_tracking(body: CreateTrackingRequest) -> Dict[str, Any]:
        """
        Create a new tracking record for a document application.

        Automatically:
        - Sets initial stage to 'submitted'
        - Calculates ETA
        - Creates an 'Application Submitted' event
        - Sends an 'upload_successful' notification to the applicant
        """
        from tracking.models import TrackingRecord

        record = TrackingRecord(
            document_id=body.document_id,
            document_type=body.document_type,
            document_name=body.document_name,
            applicant_id=body.applicant_id,
            applicant_name=body.applicant_name,
            department=body.department,
            metadata=body.metadata,
        )

        record = await db.create_tracking_record(record)

        return {
            "status": "success",
            "tracking": record.to_dict(),
            "message": f"Tracking created: {record.application_id}",
        }

    # ── POST /tracking/update/{id} ───────────────────────────────────────

    @tracking_router.post(
        "/update/{application_id}",
        summary="Update application stage",
    )
    async def update_tracking_stage(
        application_id: str,
        body: UpdateStageRequest,
    ) -> Dict[str, Any]:
        """
        Advance an application to a new stage.

        Valid stages (in order):
        submitted → verification → officer_review → issuing_authority →
        generated → printed → dispatched → delivered

        Also supports: rejected, on_hold

        Automatically:
        - Records the stage transition in history
        - Updates ETA
        - Sends a notification to the applicant
        """
        # Validate stage
        valid_stages = [s.value for s in TrackingStage]
        if body.stage not in valid_stages:
            raise HTTPException(
                400,
                f"Invalid stage: '{body.stage}'. Valid: {valid_stages}",
            )

        record = await db.update_stage(
            application_id=application_id,
            new_stage=TrackingStage(body.stage),
            officer_id=body.officer_id,
            officer_name=body.officer_name,
            department=body.department,
            notes=body.notes,
        )

        if not record:
            raise HTTPException(404, f"Tracking record not found: {application_id}")

        return {
            "status": "success",
            "tracking": record.to_dict(),
            "message": f"Stage updated to: {body.stage}",
        }

    # ── GET /notifications ───────────────────────────────────────────────

    @notif_router.get(
        "",
        summary="Get user notifications",
    )
    async def get_notifications(
        user_id: str = Query(..., description="User ID"),
        unread_only: bool = Query(False, description="Only return unread notifications"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Dict[str, Any]:
        """
        Get notifications for a user.

        Notification types:
        - upload_successful
        - verification_complete
        - manual_review
        - document_approved
        - generated
        - dispatched
        - delivered
        - suspicious_login
        - document_rejected
        - status_update
        """
        notifications = await db.get_notifications(
            user_id=user_id,
            unread_only=unread_only,
            limit=limit,
            offset=offset,
        )
        unread_count = await db.get_unread_count(user_id)

        return {
            "status": "success",
            "notifications": [n.to_dict() for n in notifications],
            "total": len(notifications),
            "unread_count": unread_count,
        }

    # ── POST /notifications/mark-read ────────────────────────────────────

    @notif_router.post(
        "/mark-read",
        summary="Mark notifications as read",
    )
    async def mark_read(body: MarkReadRequest) -> Dict[str, Any]:
        """
        Mark notifications as read.

        If notification_ids is provided, only those are marked.
        If omitted, ALL unread notifications for the user are marked as read.
        """
        count = await db.mark_notifications_read(
            user_id=body.user_id,
            notification_ids=body.notification_ids,
        )

        return {
            "status": "success",
            "marked_read": count,
            "message": f"Marked {count} notification(s) as read",
        }

    # ── GET /notifications/count ─────────────────────────────────────────

    @notif_router.get(
        "/count",
        summary="Get unread notification count",
    )
    async def get_unread_count(
        user_id: str = Query(..., description="User ID"),
    ) -> Dict[str, Any]:
        """Get the number of unread notifications for a user."""
        count = await db.get_unread_count(user_id)
        return {
            "status": "success",
            "unread_count": count,
        }

    return tracking_router, notif_router
