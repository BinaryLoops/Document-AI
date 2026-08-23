"""
generation/workflow.py — End-to-end document generation pipeline.

Workflow stages
---------------
  1. SUBMITTED  — Request saved, fields validated
  2. VERIFYING  — Supporting documents checked (existence + basic type match)
  3. CASE_CHECK — Verify no active block / prior issue for same person+type
  4. APPROVED   — Issuing authority explicitly approves (or auto-approved in dev)
  5. GENERATING — PDF assembled via pdf_builder
  6. SIGNING    — Digital signature applied
  7. COMPLETE   — Document persisted, downloadable

Any stage can produce REJECTED with a reason stored on the request.

All state transitions are audit-logged via generation/database.add_audit_event().
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from generation import database as db
from generation.database import (
    add_audit_event, get_document_by_request, get_pdf_dir, next_document_number,
    save_document, save_request,
)
from generation.digital_signature import sign_pdf_bytes
from generation.models import (
    DocumentType, GeneratedDocument, GenerationAuditEvent,
    GenerationRequest, GenerationStatus, SignatureStatus, WatermarkType,
)
from generation.pdf_builder import build_pdf
from generation.qr_generator import make_document_qr
from generation.template_engine import (
    FieldValidationError, get_display_name, get_issuing_authority_name,
    get_validity_years, validate_and_map,
)
from core.logging import get_logger

logger = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
_AUTO_APPROVE  = os.getenv("GEN_AUTO_APPROVE", "true").lower() == "true"
_REQUIRE_DOCS  = os.getenv("GEN_REQUIRE_SUPPORTING_DOCS", "false").lower() == "true"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _audit(
    request_id:    str,
    actor_user_id: str,
    action:        str,
    detail:        Optional[str] = None,
    doc_id:        Optional[str] = None,
    ip_address:    str = "",
) -> None:
    add_audit_event(GenerationAuditEvent(
        request_id=request_id,
        doc_id=doc_id,
        actor_user_id=actor_user_id,
        action=action,
        detail=detail,
        ip_address=ip_address,
    ))


def _set_status(req: GenerationRequest, status: GenerationStatus, reason: str = "") -> None:
    req.status = status
    if reason:
        req.rejection_reason = reason
    save_request(req)


# ── Stage 1: Validate and create request ─────────────────────────────────────

def create_request(
    document_type:     DocumentType,
    applicant_user_id: str,
    requested_by:      str,
    submitted_fields:  Dict[str, Any],
    department_code:   Optional[str] = None,
    issued_by:         Optional[str] = None,
    ip_address:        str = "",
) -> GenerationRequest:
    """
    Validate the submitted fields and persist the generation request.

    Raises FieldValidationError on invalid input.
    """
    # Validate fields against template
    _, norm_fields = validate_and_map(document_type, submitted_fields)

    req = GenerationRequest(
        document_type=document_type,
        applicant_user_id=applicant_user_id,
        requested_by=requested_by,
        issued_by=issued_by,
        department_code=department_code,
        fields=norm_fields,
        status=GenerationStatus.PENDING,
    )
    save_request(req)

    _audit(req.request_id, requested_by, "submitted",
           f"document_type={document_type.value}", ip_address=ip_address)

    logger.info(
        "Generation request created: %s type=%s user=%s",
        req.request_id, document_type.value, applicant_user_id,
    )
    return req


# ── Stage 2: Verify supporting documents ─────────────────────────────────────

def verify_supporting_docs(
    req:           GenerationRequest,
    actor_user_id: str,
    ip_address:    str = "",
) -> bool:
    """
    Check that required supporting docs are referenced on the request.
    In production this would cross-check the digilocker/verification_engine.
    """
    _set_status(req, GenerationStatus.VERIFYING)
    _audit(req.request_id, actor_user_id, "verifying", ip_address=ip_address)

    from generation.template_engine import get_required_supporting_docs
    required = get_required_supporting_docs(req.document_type)

    if _REQUIRE_DOCS and required and not req.supporting_docs:
        reason = f"Missing supporting documents: {', '.join(required)}"
        _set_status(req, GenerationStatus.REJECTED, reason)
        _audit(req.request_id, actor_user_id, "rejected", reason, ip_address=ip_address)
        logger.warning("Request %s rejected: %s", req.request_id, reason)
        return False

    req.verification_passed = True
    save_request(req)
    _audit(req.request_id, actor_user_id, "verification_passed", ip_address=ip_address)
    return True


# ── Stage 3: Case check ───────────────────────────────────────────────────────

def case_check(
    req:           GenerationRequest,
    actor_user_id: str,
    ip_address:    str = "",
) -> bool:
    """
    Check that no active/recent document of the same type exists for
    the applicant (prevents duplicate issuance).
    """
    _set_status(req, GenerationStatus.CASE_CHECK)
    _audit(req.request_id, actor_user_id, "case_check", ip_address=ip_address)

    existing = [
        d for d in db.get_documents_for_user(req.applicant_user_id)
        if d.document_type == req.document_type
        and not d.revoked
        and d.status == GenerationStatus.COMPLETE
    ]

    if existing:
        # For some types (passport) allow renewal; for others block duplicate
        allow_renewal = req.document_type in (
            DocumentType.PASSPORT,
            DocumentType.DRIVING_LICENSE,
        )
        if not allow_renewal:
            reason = (
                f"An active {req.document_type.value} already exists: "
                f"{existing[0].document_number}"
            )
            _set_status(req, GenerationStatus.REJECTED, reason)
            _audit(req.request_id, actor_user_id, "rejected", reason, ip_address=ip_address)
            logger.warning("Request %s blocked (duplicate): %s", req.request_id, reason)
            return False

    req.case_clear = True
    save_request(req)
    _audit(req.request_id, actor_user_id, "case_clear", ip_address=ip_address)
    return True


# ── Stage 4: Approval ─────────────────────────────────────────────────────────

def approve_request(
    req:           GenerationRequest,
    approver_id:   str,
    ip_address:    str = "",
) -> None:
    """Mark the request as approved by the issuing authority."""
    req.issued_by   = approver_id
    req.approved_at = datetime.now(timezone.utc)
    _set_status(req, GenerationStatus.APPROVED)
    _audit(req.request_id, approver_id, "approved", ip_address=ip_address)
    logger.info("Request %s approved by %s", req.request_id, approver_id)


def reject_request(
    req:           GenerationRequest,
    rejector_id:   str,
    reason:        str,
    ip_address:    str = "",
) -> None:
    """Explicitly reject a request."""
    _set_status(req, GenerationStatus.REJECTED, reason)
    _audit(req.request_id, rejector_id, "rejected", reason, ip_address=ip_address)
    logger.info("Request %s rejected by %s: %s", req.request_id, rejector_id, reason)


# ── Stage 5-7: PDF generation + signing ──────────────────────────────────────

def _get_applicant_name(req: GenerationRequest) -> str:
    """Pull the applicant's display name from the fields."""
    f = req.fields
    return (
        f.get("full_name")
        or f"{f.get('given_names', '')} {f.get('surname', '')}".strip()
        or f.get("child_name")
        or f.get("owner_name")
        or req.applicant_user_id
    )


def generate_document(
    req:           GenerationRequest,
    issuer_user_id: str,
    issuer_name:   str,
    ip_address:    str = "",
) -> GeneratedDocument:
    """
    Run stages 5-7: build PDF, sign it, persist the GeneratedDocument.

    Raises RuntimeError on any failure.
    """
    if req.status not in (GenerationStatus.APPROVED, GenerationStatus.PENDING):
        raise RuntimeError(
            f"Request {req.request_id} is in status '{req.status.value}' — "
            "must be APPROVED or PENDING to generate."
        )

    # ── Stage 5: Generate PDF ─────────────────────────────────────────────
    _set_status(req, GenerationStatus.GENERATING)
    _audit(req.request_id, issuer_user_id, "generating", ip_address=ip_address)

    doc_number     = next_document_number(req.document_type)
    applicant_name = _get_applicant_name(req)
    doc_type_name  = get_display_name(req.document_type)
    authority_name = get_issuing_authority_name(req.document_type)
    validity_years = get_validity_years(req.document_type)
    now            = datetime.now(timezone.utc)
    valid_until    = (now + timedelta(days=365 * validity_years)) if validity_years else None

    # Validate fields (second pass — ensures consistent normalised list)
    try:
        field_objs, _ = validate_and_map(req.document_type, req.fields)
    except FieldValidationError as e:
        _set_status(req, GenerationStatus.REJECTED, str(e))
        raise RuntimeError(f"Field validation failed: {e}")

    # ── QR code ───────────────────────────────────────────────────────────
    _set_status(req, GenerationStatus.SIGNING)
    _audit(req.request_id, issuer_user_id, "qr_generating", ip_address=ip_address)

    tmp_doc_id = str(__import__("uuid").uuid4())
    verify_url, qr_hash, qr_png = make_document_qr(
        doc_id=tmp_doc_id,
        document_number=doc_number,
        document_type=req.document_type.value,
        applicant_name=applicant_name,
        issued_at=now,
    )

    # ── Build PDF (unsigned first pass — signature hash added after) ──────
    pdf_bytes = build_pdf(
        document_number=doc_number,
        document_title=doc_type_name,
        issuing_authority=authority_name,
        fields=field_objs,
        issued_by_name=issuer_name,
        issued_at=now,
        department_code=req.department_code or issuer_user_id,
        watermark_type=WatermarkType.OFFICIAL,
        qr_png=qr_png,
        valid_until=valid_until,
        signature_hash="",   # placeholder — will sign and rebuild if needed
        applicant_name=applicant_name,
    )

    # ── Stage 6: Sign PDF ─────────────────────────────────────────────────
    _audit(req.request_id, issuer_user_id, "signing", ip_address=ip_address)
    sig_hash, sig_b64 = sign_pdf_bytes(pdf_bytes)

    # Rebuild PDF with real signature hash embedded in signature block
    pdf_bytes = build_pdf(
        document_number=doc_number,
        document_title=doc_type_name,
        issuing_authority=authority_name,
        fields=field_objs,
        issued_by_name=issuer_name,
        issued_at=now,
        department_code=req.department_code or issuer_user_id,
        watermark_type=WatermarkType.OFFICIAL,
        qr_png=qr_png,
        valid_until=valid_until,
        signature_hash=sig_hash,
        applicant_name=applicant_name,
    )

    # ── Stage 7: Persist ──────────────────────────────────────────────────
    pdf_dir  = get_pdf_dir()
    pdf_path = pdf_dir / f"{doc_number}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    doc = GeneratedDocument(
        doc_id=tmp_doc_id,
        request_id=req.request_id,
        document_type=req.document_type,
        document_number=doc_number,
        applicant_user_id=req.applicant_user_id,
        applicant_name=applicant_name,
        issued_by=issuer_user_id,
        department_code=req.department_code or issuer_user_id,
        issued_at=now,
        valid_from=now,
        valid_until=valid_until,
        signature_status=SignatureStatus.SIGNED,
        signature_hash=sig_hash,
        signature_value=sig_b64,
        signed_by=issuer_user_id,
        signed_at=now,
        qr_verification_url=verify_url,
        qr_payload_hash=qr_hash,
        watermark_type=WatermarkType.OFFICIAL,
        pdf_path=str(pdf_path),
        pdf_size_bytes=len(pdf_bytes),
        status=GenerationStatus.COMPLETE,
        fields=req.fields,
    )
    save_document(doc)

    req.completed_at = now
    _set_status(req, GenerationStatus.COMPLETE)
    _audit(
        req.request_id, issuer_user_id, "complete",
        f"doc_id={doc.doc_id} doc_number={doc_number}",
        doc_id=doc.doc_id,
        ip_address=ip_address,
    )

    logger.info(
        "Document issued: %s  type=%s  size=%d bytes",
        doc_number, req.document_type.value, len(pdf_bytes),
    )
    return doc


# ── Full pipeline (single-call convenience) ───────────────────────────────────

def run_full_pipeline(
    document_type:     DocumentType,
    applicant_user_id: str,
    issuer_user_id:    str,
    issuer_name:       str,
    submitted_fields:  Dict[str, Any],
    department_code:   Optional[str] = None,
    ip_address:        str = "",
) -> Tuple[GenerationRequest, GeneratedDocument]:
    """
    Run the complete workflow in one call (used by the API routes).

    Stages run: validate → verify_docs → case_check → approve → generate

    Returns (request, document).
    Raises RuntimeError or FieldValidationError on failure.
    """
    # Stage 1
    req = create_request(
        document_type=document_type,
        applicant_user_id=applicant_user_id,
        requested_by=issuer_user_id,
        submitted_fields=submitted_fields,
        department_code=department_code,
        issued_by=issuer_user_id,
        ip_address=ip_address,
    )

    # Stage 2
    if not verify_supporting_docs(req, issuer_user_id, ip_address):
        raise RuntimeError(req.rejection_reason or "Supporting document verification failed.")

    # Stage 3
    if not case_check(req, issuer_user_id, ip_address):
        raise RuntimeError(req.rejection_reason or "Case check failed.")

    # Stage 4
    if _AUTO_APPROVE:
        approve_request(req, issuer_user_id, ip_address)

    # Stages 5-7
    doc = generate_document(req, issuer_user_id, issuer_name, ip_address)
    return req, doc


# ── Revocation ────────────────────────────────────────────────────────────────

def revoke_document(
    doc:           GeneratedDocument,
    revoker_id:    str,
    reason:        str,
    ip_address:    str = "",
) -> GeneratedDocument:
    """Mark a document as revoked and rebuild its PDF with REVOKED watermark."""
    doc.revoked      = True
    doc.revoked_at   = datetime.now(timezone.utc)
    doc.revoked_by   = revoker_id
    doc.revoke_reason = reason
    doc.status       = GenerationStatus.REVOKED
    doc.watermark_type = WatermarkType.REVOKED

    # Rebuild PDF with revoked watermark
    try:
        from generation.template_engine import (
            get_display_name, get_issuing_authority_name, validate_and_map,
        )
        field_objs, _ = validate_and_map(doc.document_type, doc.fields)
        auth = get_issuing_authority_name(doc.document_type)
        title = get_display_name(doc.document_type)

        new_pdf = build_pdf(
            document_number=doc.document_number,
            document_title=title,
            issuing_authority=auth,
            fields=field_objs,
            issued_by_name=doc.issued_by,
            issued_at=doc.issued_at,
            department_code=doc.department_code,
            watermark_type=WatermarkType.REVOKED,
            qr_png=None,
            valid_until=doc.valid_until,
            signature_hash=doc.signature_hash,
            applicant_name=doc.applicant_name,
        )
        pdf_path = get_pdf_dir() / f"{doc.document_number}_REVOKED.pdf"
        pdf_path.write_bytes(new_pdf)
        doc.pdf_path      = str(pdf_path)
        doc.pdf_size_bytes = len(new_pdf)
    except Exception as e:
        logger.error("Failed to rebuild revoked PDF: %s", e)

    save_document(doc)
    _audit(
        doc.request_id, revoker_id, "revoked",
        reason, doc_id=doc.doc_id, ip_address=ip_address,
    )
    logger.info("Document %s revoked by %s: %s", doc.document_number, revoker_id, reason)
    return doc
