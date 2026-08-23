"""
generation/routes.py — All /generate/* and /generated/* API endpoints.

Endpoints (spec requirements + extras)
---------------------------------------
  POST /generate/passport          — Generate Passport
  POST /generate/license           — Generate Driving Licence
  POST /generate/birth             — Generate Birth Certificate
  POST /generate/income            — Generate Income Certificate
  POST /generate/land              — Generate Land Record
  GET  /generated/{id}             — Download the generated PDF
  GET  /generate/status/{id}       — Poll generation request status
  GET  /generate/list              — List all documents (admin / issuing auth)
  GET  /generate/my                — List documents issued TO current user
  GET  /generate/requests          — List pending requests (issuing auth)
  POST /generate/approve/{req_id}  — Approve a pending request
  POST /generate/reject/{req_id}   — Reject a pending request
  POST /generate/revoke/{doc_id}   — Revoke an issued document
  GET  /generate/verify/{doc_number} — Public document verification (QR scan)
  GET  /generate/template/{type}   — Get field schema for a document type
  GET  /generate/pubkey            — Public signing key (PEM, for verification)

RBAC
----
  All POST /generate/* require Permission.GENERATE_DOCUMENT (Issuing Authority only).
  GET /generated/{id} is accessible to the document owner or issuing authorities.
  GET /generate/verify/* is public (no auth required — for QR scan).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from auth.models import Role, User
from auth.rbac import Permission, optional_auth, require_auth, require_permission, require_role
from generation import database as db
from generation.digital_signature import get_key_fingerprint, get_public_key_pem, verify_signature
from generation.models import DocumentType, GenerationStatus
from generation.template_engine import (
    FieldValidationError, get_display_name, get_template_field_list,
)
from generation.workflow import (
    approve_request, case_check, create_request, generate_document,
    reject_request, revoke_document, run_full_pipeline,
    verify_supporting_docs,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/generate", tags=["document-generation"])


# ── Request / Response models ─────────────────────────────────────────────────

class GenerationPayload(BaseModel):
    """Common wrapper for all generation requests."""
    applicant_user_id: Optional[str] = Field(
        None,
        description="User ID of the person this document is for. "
                    "Defaults to the authenticated user if omitted.",
    )
    fields: Dict[str, Any] = Field(..., description="Document field values")


class ApprovalPayload(BaseModel):
    notes: Optional[str] = None


class RejectionPayload(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class RevocationPayload(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_ip(request: Request) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _issuer_name(user: User) -> str:
    """Human-readable name for the issuing officer."""
    return user.full_name or user.employee_id or user.user_id


def _run_generation(
    doc_type: DocumentType,
    payload:  GenerationPayload,
    user:     User,
    request:  Request,
) -> Dict[str, Any]:
    """Shared generation logic for all five document types."""
    applicant_id = payload.applicant_user_id or user.user_id
    try:
        req, doc = run_full_pipeline(
            document_type=doc_type,
            applicant_user_id=applicant_id,
            issuer_user_id=user.user_id,
            issuer_name=_issuer_name(user),
            submitted_fields=payload.fields,
            department_code=user.department_code,
            ip_address=_get_ip(request),
        )
    except FieldValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Field validation failed", "errors": e.errors},
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return {
        "status":          "success",
        "request_id":      req.request_id,
        "document_id":     doc.doc_id,
        "document_number": doc.document_number,
        "document_type":   doc.document_type.value,
        "applicant_name":  doc.applicant_name,
        "issued_at":       doc.issued_at.isoformat(),
        "valid_until":     doc.valid_until.isoformat() if doc.valid_until else None,
        "signature_status": doc.signature_status.value,
        "qr_verification_url": doc.qr_verification_url,
        "download_url":    f"/generated/{doc.doc_id}",
        "pdf_size_bytes":  doc.pdf_size_bytes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Generation endpoints (Issuing Authority only)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/request/{doc_type}",
    summary="Submit a document generation request",
)
async def request_document(
    doc_type: str,
    payload: GenerationPayload,
    request: Request,
    user: User = Depends(require_auth),
) -> Dict[str, Any]:
    """Create a pending request for the authenticated user to be reviewed."""
    try:
        document_type = DocumentType(doc_type)
    except ValueError:
        raise HTTPException(status_code=404, detail="Unsupported document type")

    applicant_id = payload.applicant_user_id or user.user_id
    if user.role == Role.CITIZEN and applicant_id != user.user_id:
        raise HTTPException(status_code=403, detail="Citizens may only request documents for themselves")

    try:
        generation_request = create_request(
            document_type=document_type,
            applicant_user_id=applicant_id,
            requested_by=user.user_id,
            submitted_fields=payload.fields,
            department_code=user.department_code,
            ip_address=_get_ip(request),
        )
    except FieldValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Field validation failed", "errors": e.errors},
        )

    return {
        "status": "submitted",
        "message": "Document request submitted for review",
        "request_id": generation_request.request_id,
        "document_type": generation_request.document_type.value,
        "request": generation_request.to_dict(),
    }

@router.post(
    "/passport",
    summary="Generate Passport",
    dependencies=[Depends(require_permission(Permission.GENERATE_DOCUMENT))],
)
async def generate_passport(
    payload: GenerationPayload,
    request: Request,
    user:    User = Depends(require_permission(Permission.GENERATE_DOCUMENT)),
) -> Dict[str, Any]:
    """
    Generate an official Passport document.

    Required fields: surname, given_names, date_of_birth, place_of_birth,
    gender, nationality, aadhaar_number, father_name, mother_name,
    address, application_type.
    """
    return _run_generation(DocumentType.PASSPORT, payload, user, request)


@router.post(
    "/license",
    summary="Generate Driving Licence",
    dependencies=[Depends(require_permission(Permission.GENERATE_DOCUMENT))],
)
async def generate_license(
    payload: GenerationPayload,
    request: Request,
    user:    User = Depends(require_permission(Permission.GENERATE_DOCUMENT)),
) -> Dict[str, Any]:
    """
    Generate an official Driving Licence.

    Required fields: full_name, date_of_birth, blood_group, gender,
    address, pincode, vehicle_classes, rto_code, state,
    aadhaar_number, father_or_spouse.
    """
    return _run_generation(DocumentType.DRIVING_LICENSE, payload, user, request)


@router.post(
    "/birth",
    summary="Generate Birth Certificate",
    dependencies=[Depends(require_permission(Permission.GENERATE_DOCUMENT))],
)
async def generate_birth(
    payload: GenerationPayload,
    request: Request,
    user:    User = Depends(require_permission(Permission.GENERATE_DOCUMENT)),
) -> Dict[str, Any]:
    """
    Generate an official Birth Certificate.

    Required fields: child_name, date_of_birth, place_of_birth, gender,
    father_name, mother_name, permanent_address, registration_date.
    """
    return _run_generation(DocumentType.BIRTH_CERTIFICATE, payload, user, request)


@router.post(
    "/income",
    summary="Generate Income Certificate",
    dependencies=[Depends(require_permission(Permission.GENERATE_DOCUMENT))],
)
async def generate_income(
    payload: GenerationPayload,
    request: Request,
    user:    User = Depends(require_permission(Permission.GENERATE_DOCUMENT)),
) -> Dict[str, Any]:
    """
    Generate an official Income Certificate.

    Required fields: full_name, date_of_birth, gender, address,
    aadhaar_number, annual_income, income_source, purpose, father_name.
    """
    return _run_generation(DocumentType.INCOME_CERTIFICATE, payload, user, request)


@router.post(
    "/land",
    summary="Generate Land Record (Patta / RoR)",
    dependencies=[Depends(require_permission(Permission.GENERATE_DOCUMENT))],
)
async def generate_land(
    payload: GenerationPayload,
    request: Request,
    user:    User = Depends(require_permission(Permission.GENERATE_DOCUMENT)),
) -> Dict[str, Any]:
    """
    Generate an official Land Record.

    Required fields: owner_name, father_name, owner_address, aadhaar_number,
    survey_number, area, land_type, village, tehsil, district, state,
    transaction_type.
    """
    return _run_generation(DocumentType.LAND_RECORD, payload, user, request)


# ─────────────────────────────────────────────────────────────────────────────
# Workflow management (Issuing Authority)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/requests",
    summary="List pending generation requests",
    dependencies=[Depends(require_permission(Permission.GENERATE_DOCUMENT))],
)
async def list_requests(
    status_filter: Optional[str] = Query(None, alias="status"),
    doc_type:      Optional[str] = Query(None),
    limit:         int           = Query(50, ge=1, le=200),
    offset:        int           = Query(0, ge=0),
    user:          User          = Depends(require_permission(Permission.GENERATE_DOCUMENT)),
) -> Dict[str, Any]:
    """List all generation requests visible to the issuing authority."""
    st = GenerationStatus(status_filter) if status_filter else None
    dt = DocumentType(doc_type) if doc_type else None
    reqs = db.get_all_requests(status=st, doc_type=dt, limit=limit, offset=offset)
    return {
        "requests": [r.to_dict() for r in reqs],
        "count":    len(reqs),
        "offset":   offset,
    }


@router.post(
    "/approve/{request_id}",
    summary="Approve a pending generation request",
    dependencies=[Depends(require_permission(Permission.GENERATE_DOCUMENT))],
)
async def approve_generation_request(
    request_id: str,
    body:       ApprovalPayload,
    request:    Request,
    user:       User = Depends(require_permission(Permission.GENERATE_DOCUMENT)),
) -> Dict[str, Any]:
    """Approve a request that is in PENDING / CASE_CHECK status."""
    req = db.get_request(request_id)
    if req is None:
        raise HTTPException(404, f"Request {request_id} not found.")
    if req.status not in (
        GenerationStatus.PENDING, GenerationStatus.CASE_CHECK, GenerationStatus.VERIFYING
    ):
        raise HTTPException(400, f"Request is in status '{req.status.value}' — cannot approve.")

    approve_request(req, user.user_id, _get_ip(request))

    # Auto-generate after approval
    try:
        doc = generate_document(req, user.user_id, _issuer_name(user), _get_ip(request))
        return {
            "status":          "generated",
            "request_id":      req.request_id,
            "document_id":     doc.doc_id,
            "document_number": doc.document_number,
            "download_url":    f"/generated/{doc.doc_id}",
        }
    except Exception as e:
        raise HTTPException(500, f"Approval succeeded but generation failed: {e}")


@router.post(
    "/reject/{request_id}",
    summary="Reject a pending generation request",
    dependencies=[Depends(require_permission(Permission.GENERATE_DOCUMENT))],
)
async def reject_generation_request(
    request_id: str,
    body:       RejectionPayload,
    request:    Request,
    user:       User = Depends(require_permission(Permission.GENERATE_DOCUMENT)),
) -> Dict[str, Any]:
    """Reject a pending request with a mandatory reason."""
    req = db.get_request(request_id)
    if req is None:
        raise HTTPException(404, f"Request {request_id} not found.")
    reject_request(req, user.user_id, body.reason, _get_ip(request))
    return {"status": "rejected", "request_id": request_id, "reason": body.reason}


@router.post(
    "/revoke/{doc_id}",
    summary="Revoke an issued document",
    dependencies=[Depends(require_permission(Permission.REVOKE_DOCUMENT))],
)
async def revoke_issued_document(
    doc_id:  str,
    body:    RevocationPayload,
    request: Request,
    user:    User = Depends(require_permission(Permission.REVOKE_DOCUMENT)),
) -> Dict[str, Any]:
    """
    Revoke an issued document.  Rebuilds the PDF with a REVOKED watermark.
    Only Issuing Authority with REVOKE_DOCUMENT permission.
    """
    doc = db.get_document(doc_id)
    if doc is None:
        raise HTTPException(404, f"Document {doc_id} not found.")
    if doc.revoked:
        raise HTTPException(400, "Document is already revoked.")
    doc = revoke_document(doc, user.user_id, body.reason, _get_ip(request))
    return {
        "status":          "revoked",
        "doc_id":          doc.doc_id,
        "document_number": doc.document_number,
        "revoked_at":      doc.revoked_at.isoformat() if doc.revoked_at else None,
        "reason":          doc.revoke_reason,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Download
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/status/{request_id}",
    summary="Poll generation request status",
)
async def get_generation_status(
    request_id: str,
    user: User = Depends(require_auth),
) -> Dict[str, Any]:
    """Return current status and progress of a generation request."""
    req = db.get_request(request_id)
    if req is None:
        raise HTTPException(404, f"Request {request_id} not found.")

    # Citizens can only see their own requests
    if (
        user.role == Role.CITIZEN
        and req.applicant_user_id != user.user_id
    ):
        raise HTTPException(403, "Access denied.")

    result = req.to_dict()
    # Attach document if complete
    doc = db.get_document_by_request(request_id)
    if doc:
        result["document"] = doc.to_public_dict()
        result["download_url"] = f"/generated/{doc.doc_id}"

    return result


@router.get(
    "/list",
    summary="List all issued documents (admin or issuing authority)",
)
async def list_all_documents(
    doc_type: Optional[str] = Query(None),
    limit:    int           = Query(50, ge=1, le=200),
    offset:   int           = Query(0, ge=0),
    user:     User          = Depends(require_role(
        Role.SYSTEM_ADMIN, Role.ISSUING_AUTHORITY
    )),
) -> Dict[str, Any]:
    """List all issued documents. Admin and Issuing Authority only."""
    dt   = DocumentType(doc_type) if doc_type else None
    docs = db.get_all_documents(doc_type=dt, limit=limit, offset=offset)
    return {
        "documents": [d.to_public_dict() for d in docs],
        "count":     len(docs),
        "offset":    offset,
    }


@router.get(
    "/my",
    summary="List documents issued to the current user",
)
async def my_documents(
    user: User = Depends(require_auth),
) -> Dict[str, Any]:
    """Return all documents issued to the authenticated user."""
    docs = db.get_documents_for_user(user.user_id)
    return {
        "user_id":   user.user_id,
        "documents": [d.to_public_dict() for d in docs],
        "count":     len(docs),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Download endpoint  (spec: GET /generated/{id})
# ─────────────────────────────────────────────────────────────────────────────

download_router = APIRouter(prefix="/generated", tags=["document-generation"])


@download_router.get(
    "/{doc_id}",
    summary="Download an issued document as PDF",
)
async def download_document(
    doc_id: str,
    user:   User = Depends(require_auth),
) -> FileResponse:
    """
    Download the generated PDF for a document.

    - Citizens can only download their own documents.
    - Issuing Authority and Admin can download any document.
    """
    doc = db.get_document(doc_id)
    if doc is None:
        raise HTTPException(404, f"Document {doc_id} not found.")

    # Ownership check
    if (
        user.role == Role.CITIZEN
        and doc.applicant_user_id != user.user_id
    ):
        raise HTTPException(403, "You can only download your own documents.")

    pdf_path = Path(doc.pdf_path)
    if not pdf_path.exists():
        raise HTTPException(
            404,
            f"PDF file not found on server. Document ID: {doc_id}",
        )

    safe_name = f"{doc.document_number}.pdf"
    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=safe_name,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "X-Document-Number":   doc.document_number,
            "X-Document-Type":     doc.document_type.value,
            "X-Signature-Status":  doc.signature_status.value,
        },
    )


@download_router.get(
    "/{doc_id}/metadata",
    summary="Get document metadata (no download)",
)
async def document_metadata(
    doc_id: str,
    user:   User = Depends(require_auth),
) -> Dict[str, Any]:
    """Return the public metadata for a generated document."""
    doc = db.get_document(doc_id)
    if doc is None:
        raise HTTPException(404, f"Document {doc_id} not found.")
    if (
        user.role == Role.CITIZEN
        and doc.applicant_user_id != user.user_id
    ):
        raise HTTPException(403, "Access denied.")
    return doc.to_public_dict()


@download_router.get(
    "/{doc_id}/audit",
    summary="Get generation audit trail for a document",
    dependencies=[Depends(require_role(Role.SYSTEM_ADMIN, Role.ISSUING_AUTHORITY))],
)
async def document_audit(doc_id: str) -> Dict[str, Any]:
    """Return the full audit trail for a document's generation lifecycle."""
    doc = db.get_document(doc_id)
    if doc is None:
        raise HTTPException(404, f"Document {doc_id} not found.")
    events = db.get_audit_for_request(doc.request_id)
    return {
        "doc_id":     doc_id,
        "request_id": doc.request_id,
        "events":     [e.to_dict() for e in events],
        "count":      len(events),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Public verification endpoint (no auth — for QR scan)
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/verify/{document_number}",
    summary="Public document verification (QR scan — no auth required)",
    tags=["document-verification"],
)
async def verify_document(document_number: str) -> Dict[str, Any]:
    """
    Publicly verify a document by its number.
    Returns validity, issue date, and document type — no PII exposed.
    Called by QR code scanners.
    """
    doc = db.get_document_by_number(document_number)
    if doc is None:
        return JSONResponse(
            status_code=404,
            content={
                "valid":           False,
                "document_number": document_number,
                "message":         "Document not found in the system.",
            },
        )

    # Validate digital signature against stored PDF
    sig_valid = False
    if doc.pdf_path and Path(doc.pdf_path).exists():
        try:
            pdf_bytes = Path(doc.pdf_path).read_bytes()
            sig_valid = verify_signature(pdf_bytes, doc.signature_value)
        except Exception:
            sig_valid = False

    return {
        "valid":             not doc.revoked and doc.status.value == "complete",
        "document_number":   doc.document_number,
        "document_type":     doc.document_type.value,
        "issued_at":         doc.issued_at.isoformat(),
        "valid_until":       doc.valid_until.isoformat() if doc.valid_until else "Lifetime",
        "issuing_department": doc.department_code,
        "revoked":           doc.revoked,
        "revoke_reason":     doc.revoke_reason if doc.revoked else None,
        "signature_valid":   sig_valid,
        "status":            doc.status.value,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Template info + public key
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/template/{doc_type}",
    summary="Get field schema for a document type",
    tags=["document-generation"],
)
async def get_template_schema(doc_type: str) -> Dict[str, Any]:
    """
    Return the list of fields expected for a given document type.
    Useful for clients to build dynamic forms.
    """
    try:
        dt = DocumentType(doc_type)
    except ValueError:
        raise HTTPException(
            400,
            f"Unknown document type '{doc_type}'. "
            f"Valid: {[t.value for t in DocumentType]}",
        )
    from generation.template_engine import (
        get_display_name, get_issuing_authority_name,
        get_required_supporting_docs, get_validity_years,
    )
    return {
        "document_type":        dt.value,
        "display_name":         get_display_name(dt),
        "issuing_authority":    get_issuing_authority_name(dt),
        "validity_years":       get_validity_years(dt),
        "required_supporting_docs": get_required_supporting_docs(dt),
        "fields":               get_template_field_list(dt),
    }


@router.get(
    "/pubkey",
    summary="Get the document signing public key (PEM)",
    tags=["document-verification"],
)
async def get_signing_public_key() -> Dict[str, Any]:
    """
    Return the RSA public key used to sign all generated documents.
    Clients can use this to independently verify document signatures.
    """
    return {
        "algorithm":   "RSA-2048 PKCS1v15 SHA-256",
        "fingerprint": get_key_fingerprint(),
        "public_key_pem": get_public_key_pem(),
    }


# Export both routers so main.py can include both
__all__ = ["router", "download_router"]
