"""
digilocker/routes.py — FastAPI endpoints for the Government Digital Locker.

Endpoints:
  POST /documents/upload          — Upload document (full pipeline)
  GET  /documents                 — List documents (paginated, filterable)
  GET  /documents/categories      — List all document categories
  GET  /documents/search          — Search documents
  GET  /documents/{id}            — Get document metadata
  GET  /documents/{id}/download   — Download decrypted document
  GET  /documents/{id}/preview    — Get preview image
  GET  /documents/{id}/thumbnail  — Get thumbnail image
  GET  /documents/{id}/versions   — Get version history
  POST /documents/archive         — Archive a document
  POST /documents/request-delete  — Request deletion (requires approval)
  GET  /documents/deletion-requests         — List pending deletions (admin)
  POST /documents/deletion-requests/{id}/approve — Approve deletion (admin)
  POST /documents/deletion-requests/{id}/reject  — Reject deletion (admin)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from digilocker.database import DocumentDatabase
from digilocker.models import (
    AuditAction,
    AuditRecord,
    DeletionRequest,
    DeletionStatus,
    DocumentCategory,
    DocumentLifecycle,
    VerificationStatus,
)
from digilocker.pipeline import DocumentPipeline

logger = logging.getLogger(__name__)


# ── Pydantic request/response models ────────────────────────────────────────

class ArchiveRequest(BaseModel):
    document_id: str
    reason: str = ""


class DeleteRequest(BaseModel):
    document_id: str
    reason: str = ""


class DeletionReviewRequest(BaseModel):
    reason: str = ""


class DocumentListResponse(BaseModel):
    documents: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int


# ── Router factory ───────────────────────────────────────────────────────────

def create_digilocker_router(
    pipeline: DocumentPipeline,
    db: DocumentDatabase,
) -> APIRouter:
    """Create and return the DigiLocker API router."""

    router = APIRouter(prefix="/documents", tags=["Digital Locker"])

    # ── POST /documents/upload ───────────────────────────────────────────

    @router.post("/upload", summary="Upload a document through the full pipeline")
    async def upload_document(
        request: Request,
        file: UploadFile = File(...),
        owner: str = Form(...),
        department: str = Form(""),
        case_type: str = Form(""),
        serial_number: str = Form(""),
    ) -> Dict[str, Any]:
        """
        Upload a document — runs the full pipeline:
        Upload → Scan → OCR → Classification → Verification → Encryption → Storage.

        Supported formats: PDF, JPG, PNG, DOCX.
        """
        # Read file bytes
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(400, "Empty file")

        # Size limit (20 MB)
        if len(file_bytes) > 20 * 1024 * 1024:
            raise HTTPException(413, "File too large (max 20 MB)")

        try:
            doc = await pipeline.ingest(
                file_bytes=file_bytes,
                filename=file.filename or "unknown",
                owner=owner,
                department=department,
                case_type=case_type,
                serial_number=serial_number,
                mime_type=file.content_type or "",
                user_id=owner,
                ip_address=request.client.host if request.client else "",
            )
            return {
                "status": "success",
                "message": "Document uploaded and processed successfully",
                "document": doc.to_public_dict(),
            }
        except ValueError as e:
            raise HTTPException(400, str(e))
        except Exception as e:
            logger.error("Upload failed: %s", e, exc_info=True)
            raise HTTPException(500, f"Upload failed: {e}")

    # ── GET /documents ───────────────────────────────────────────────────

    @router.get("", summary="List documents with filters and pagination")
    async def list_documents(
        owner: Optional[str] = Query(None),
        document_type: Optional[str] = Query(None),
        department: Optional[str] = Query(None),
        lifecycle: Optional[str] = Query(None),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> DocumentListResponse:
        """List documents with optional filters. Soft-deleted documents are excluded."""
        docs = await db.list_documents(
            owner=owner,
            document_type=document_type,
            department=department,
            lifecycle=lifecycle,
            limit=limit,
            offset=offset,
        )
        total = await db.count_documents(
            owner=owner,
            document_type=document_type,
            department=department,
            lifecycle=lifecycle,
        )
        return DocumentListResponse(
            documents=[d.to_public_dict() for d in docs],
            total=total,
            limit=limit,
            offset=offset,
        )

    # ── GET /documents/categories ────────────────────────────────────────

    @router.get("/categories", summary="List all document categories")
    async def list_categories() -> Dict[str, Any]:
        """Return all supported document categories with schema info."""
        return {
            "categories": DocumentPipeline.get_supported_categories(),
        }

    # ── GET /documents/search ────────────────────────────────────────────

    @router.get("/search", summary="Search documents")
    async def search_documents(
        q: Optional[str] = Query(None, description="Free-text search"),
        owner: Optional[str] = Query(None),
        department: Optional[str] = Query(None),
        document_type: Optional[str] = Query(None),
        serial_number: Optional[str] = Query(None),
        date_from: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
        date_to: Optional[str] = Query(None, description="ISO date YYYY-MM-DD"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Dict[str, Any]:
        """Search documents by text, owner, department, type, serial number, or date range."""
        docs = await db.search_documents(
            query=q,
            owner=owner,
            department=department,
            document_type=document_type,
            serial_number=serial_number,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
        return {
            "results": [d.to_public_dict() for d in docs],
            "count": len(docs),
            "query": q,
        }

    # ── GET /documents/{id} ──────────────────────────────────────────────

    @router.get("/{document_id}", summary="Get document metadata")
    async def get_document(document_id: str, request: Request) -> Dict[str, Any]:
        """Get full document metadata by ID."""
        doc = await db.get_document(document_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        if doc.lifecycle == DocumentLifecycle.DELETED:
            raise HTTPException(410, "Document has been deleted")

        # Audit log
        await db.log_audit(AuditRecord(
            document_id=document_id,
            user_id="",
            action=AuditAction.VIEW,
            ip_address=request.client.host if request.client else "",
        ))

        return {"document": doc.to_public_dict()}

    # ── GET /documents/{id}/download ─────────────────────────────────────

    @router.get("/{document_id}/download", summary="Download decrypted document")
    async def download_document(document_id: str, request: Request) -> Response:
        """Download the original decrypted document."""
        doc = await db.get_document(document_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        if doc.lifecycle == DocumentLifecycle.DELETED:
            raise HTTPException(410, "Document has been deleted")

        try:
            file_bytes = await pipeline.retrieve(document_id)
        except FileNotFoundError:
            raise HTTPException(404, "Document file not found in vault")
        except PermissionError:
            raise HTTPException(403, "Document access denied")

        # Audit log
        await db.log_audit(AuditRecord(
            document_id=document_id,
            user_id="",
            action=AuditAction.DOWNLOAD,
            ip_address=request.client.host if request.client else "",
        ))

        return Response(
            content=file_bytes,
            media_type=doc.mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{doc.original_filename}"'
            },
        )

    # ── GET /documents/{id}/preview ──────────────────────────────────────

    @router.get("/{document_id}/preview", summary="Get document preview image")
    async def get_preview(document_id: str) -> Response:
        """Return the preview image (PNG) for a document."""
        doc = await db.get_document(document_id)
        if not doc:
            raise HTTPException(404, "Document not found")

        preview_bytes = pipeline.vault.retrieve_preview(document_id)
        if not preview_bytes:
            raise HTTPException(404, "Preview not available")

        return Response(content=preview_bytes, media_type="image/png")

    # ── GET /documents/{id}/thumbnail ────────────────────────────────────

    @router.get("/{document_id}/thumbnail", summary="Get document thumbnail")
    async def get_thumbnail(document_id: str) -> Response:
        """Return the thumbnail image (PNG) for a document."""
        doc = await db.get_document(document_id)
        if not doc:
            raise HTTPException(404, "Document not found")

        thumb_bytes = pipeline.vault.retrieve_thumbnail(document_id)
        if not thumb_bytes:
            raise HTTPException(404, "Thumbnail not available")

        return Response(content=thumb_bytes, media_type="image/png")

    # ── GET /documents/{id}/versions ─────────────────────────────────────

    @router.get("/{document_id}/versions", summary="Get version history")
    async def get_versions(document_id: str) -> Dict[str, Any]:
        """Get immutable version history for a document."""
        doc = await db.get_document(document_id)
        if not doc:
            raise HTTPException(404, "Document not found")

        versions = await db.get_versions(document_id)
        return {
            "document_id": document_id,
            "current_version": doc.version,
            "versions": [v.to_dict() for v in versions],
        }

    # ── POST /documents/archive ──────────────────────────────────────────

    @router.post("/archive", summary="Archive a document")
    async def archive_document(
        body: ArchiveRequest, request: Request
    ) -> Dict[str, Any]:
        """Set a document's lifecycle to ARCHIVED."""
        doc = await db.get_document(body.document_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        if doc.lifecycle == DocumentLifecycle.DELETED:
            raise HTTPException(410, "Cannot archive a deleted document")

        await db.update_lifecycle(body.document_id, DocumentLifecycle.ARCHIVED)

        await db.log_audit(AuditRecord(
            document_id=body.document_id,
            user_id="",
            action=AuditAction.ARCHIVE,
            detail=body.reason,
            ip_address=request.client.host if request.client else "",
        ))

        return {"status": "archived", "document_id": body.document_id}

    # ── POST /documents/request-delete ───────────────────────────────────

    @router.post("/request-delete", summary="Request document deletion")
    async def request_delete(
        body: DeleteRequest, request: Request
    ) -> Dict[str, Any]:
        """
        Request deletion of a document. Requires admin approval.
        No permanent deletion — approved requests soft-delete only.
        """
        doc = await db.get_document(body.document_id)
        if not doc:
            raise HTTPException(404, "Document not found")
        if doc.lifecycle == DocumentLifecycle.DELETED:
            raise HTTPException(410, "Document already deleted")
        if doc.lifecycle == DocumentLifecycle.DELETE_REQUESTED:
            raise HTTPException(409, "Deletion already requested for this document")

        # Update lifecycle
        await db.update_lifecycle(
            body.document_id, DocumentLifecycle.DELETE_REQUESTED
        )

        # Create deletion request
        del_req = DeletionRequest(
            document_id=body.document_id,
            requested_by="",  # would come from auth context
            reason=body.reason,
        )
        await db.insert_deletion_request(del_req)

        # Audit log
        await db.log_audit(AuditRecord(
            document_id=body.document_id,
            user_id="",
            action=AuditAction.DELETE_REQUEST,
            detail=body.reason,
            ip_address=request.client.host if request.client else "",
        ))

        return {
            "status": "delete_requested",
            "request_id": del_req.request_id,
            "document_id": body.document_id,
            "message": "Deletion request submitted. Requires admin approval.",
        }

    # ── GET /documents/deletion-requests ─────────────────────────────────

    @router.get("/deletion-requests", summary="List deletion requests (admin)")
    async def list_deletion_requests(
        status: Optional[str] = Query(None),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ) -> Dict[str, Any]:
        """List deletion requests. Admin-only endpoint."""
        requests = await db.list_deletion_requests(
            status=status, limit=limit, offset=offset
        )
        return {
            "requests": [r.to_dict() for r in requests],
            "count": len(requests),
        }

    # ── POST /documents/deletion-requests/{id}/approve ───────────────────

    @router.post(
        "/deletion-requests/{request_id}/approve",
        summary="Approve deletion request (admin)",
    )
    async def approve_deletion(
        request_id: str, body: DeletionReviewRequest, request: Request
    ) -> Dict[str, Any]:
        """
        Approve a deletion request. Admin-only.
        This performs a SOFT DELETE — encrypted data remains in vault.
        No permanent deletion is possible.
        """
        del_req = await db.get_deletion_request(request_id)
        if not del_req:
            raise HTTPException(404, "Deletion request not found")
        if del_req.status != DeletionStatus.PENDING:
            raise HTTPException(409, f"Request already {del_req.status.value}")

        # Approve the request
        del_req.status = DeletionStatus.APPROVED
        del_req.approved_by = "admin"  # would come from auth context
        del_req.reviewed_at = datetime.now(timezone.utc)
        await db.update_deletion_request(del_req)

        # Soft-delete the document
        await db.update_lifecycle(del_req.document_id, DocumentLifecycle.DELETED)

        # Audit log
        await db.log_audit(AuditRecord(
            document_id=del_req.document_id,
            user_id="admin",
            action=AuditAction.DELETE_APPROVE,
            detail=f"Approved: {body.reason}" if body.reason else "Approved",
            ip_address=request.client.host if request.client else "",
        ))

        return {
            "status": "approved",
            "request_id": request_id,
            "document_id": del_req.document_id,
            "message": "Document soft-deleted. Encrypted data remains in vault.",
        }

    # ── POST /documents/deletion-requests/{id}/reject ────────────────────

    @router.post(
        "/deletion-requests/{request_id}/reject",
        summary="Reject deletion request (admin)",
    )
    async def reject_deletion(
        request_id: str, body: DeletionReviewRequest, request: Request
    ) -> Dict[str, Any]:
        """Reject a deletion request. Admin-only."""
        del_req = await db.get_deletion_request(request_id)
        if not del_req:
            raise HTTPException(404, "Deletion request not found")
        if del_req.status != DeletionStatus.PENDING:
            raise HTTPException(409, f"Request already {del_req.status.value}")

        # Reject
        del_req.status = DeletionStatus.REJECTED
        del_req.approved_by = "admin"
        del_req.reviewed_at = datetime.now(timezone.utc)
        await db.update_deletion_request(del_req)

        # Restore document lifecycle
        await db.update_lifecycle(del_req.document_id, DocumentLifecycle.ACTIVE)

        # Audit log
        await db.log_audit(AuditRecord(
            document_id=del_req.document_id,
            user_id="admin",
            action=AuditAction.DELETE_REJECT,
            detail=f"Rejected: {body.reason}" if body.reason else "Rejected",
            ip_address=request.client.host if request.client else "",
        ))

        return {
            "status": "rejected",
            "request_id": request_id,
            "document_id": del_req.document_id,
        }

    return router
