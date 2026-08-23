"""
generation/database.py — In-memory + JSON-persisted stores.

Mirrors the exact pattern of auth/database.py:
  - Module-level singletons
  - threading.RLock for writes
  - load() called at startup, flush() called at shutdown
  - Lookup helpers return Optional[T]

Stores
------
  _requests  : dict[request_id, GenerationRequest]
  _documents : dict[doc_id, GeneratedDocument]
  _audit     : list[GenerationAuditEvent]  (ring-buffer, max 10 000)
  _doc_number_counter : dict[doc_type_value, int]
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from generation.models import (
    DocumentType, GeneratedDocument, GenerationAuditEvent,
    GenerationRequest, GenerationStatus, SignatureStatus,
    SupportingDocument, WatermarkType,
)
from core.logging import get_logger

logger = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
_STORE_PATH   = Path(os.getenv("GEN_STORE_PATH", "gen_store.json"))
_PDF_DIR      = Path(os.getenv("GEN_PDF_DIR",   "generated_pdfs"))
_MAX_AUDIT    = 10_000
_lock         = threading.RLock()

# ── In-memory stores ─────────────────────────────────────────────────────────
_requests:   Dict[str, GenerationRequest]   = {}
_documents:  Dict[str, GeneratedDocument]   = {}
_audit:      List[GenerationAuditEvent]     = []
_counters:   Dict[str, int]                 = {}   # doc_type → last seq number


# ── PDF directory ─────────────────────────────────────────────────────────────
def get_pdf_dir() -> Path:
    _PDF_DIR.mkdir(parents=True, exist_ok=True)
    return _PDF_DIR


# ── Document number generation ────────────────────────────────────────────────
_TYPE_PREFIX = {
    DocumentType.PASSPORT:           "PP",
    DocumentType.DRIVING_LICENSE:    "DL",
    DocumentType.BIRTH_CERTIFICATE:  "BC",
    DocumentType.INCOME_CERTIFICATE: "IC",
    DocumentType.LAND_RECORD:        "LR",
}

def next_document_number(doc_type: DocumentType) -> str:
    """Return a unique, sequential document number like IND-PP-2026-000042."""
    with _lock:
        key     = doc_type.value
        seq     = _counters.get(key, 0) + 1
        _counters[key] = seq
        year    = datetime.now(timezone.utc).year
        prefix  = _TYPE_PREFIX.get(doc_type, "XX")
        return f"IND-{prefix}-{year}-{seq:06d}"


# ── Request store ─────────────────────────────────────────────────────────────
def get_request(request_id: str) -> Optional[GenerationRequest]:
    return _requests.get(request_id)

def get_requests_for_user(user_id: str) -> List[GenerationRequest]:
    return [r for r in _requests.values() if r.applicant_user_id == user_id]

def get_all_requests(
    status: Optional[GenerationStatus] = None,
    doc_type: Optional[DocumentType]   = None,
    limit: int = 50,
    offset: int = 0,
) -> List[GenerationRequest]:
    result = list(_requests.values())
    if status:
        result = [r for r in result if r.status == status]
    if doc_type:
        result = [r for r in result if r.document_type == doc_type]
    result.sort(key=lambda r: r.submitted_at, reverse=True)
    return result[offset : offset + limit]

def save_request(req: GenerationRequest) -> None:
    with _lock:
        req.touch()
        _requests[req.request_id] = req


# ── Document store ────────────────────────────────────────────────────────────
def get_document(doc_id: str) -> Optional[GeneratedDocument]:
    return _documents.get(doc_id)

def get_document_by_number(doc_number: str) -> Optional[GeneratedDocument]:
    for d in _documents.values():
        if d.document_number == doc_number:
            return d
    return None

def get_document_by_request(request_id: str) -> Optional[GeneratedDocument]:
    for d in _documents.values():
        if d.request_id == request_id:
            return d
    return None

def get_documents_for_user(user_id: str) -> List[GeneratedDocument]:
    return [d for d in _documents.values() if d.applicant_user_id == user_id]

def get_all_documents(
    doc_type: Optional[DocumentType] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[GeneratedDocument]:
    result = list(_documents.values())
    if doc_type:
        result = [d for d in result if d.document_type == doc_type]
    result.sort(key=lambda d: d.issued_at, reverse=True)
    return result[offset : offset + limit]

def save_document(doc: GeneratedDocument) -> None:
    with _lock:
        _documents[doc.doc_id] = doc


# ── Audit log ─────────────────────────────────────────────────────────────────
def add_audit_event(event: GenerationAuditEvent) -> None:
    with _lock:
        _audit.append(event)
        if len(_audit) > _MAX_AUDIT:
            del _audit[: len(_audit) - _MAX_AUDIT]

def get_audit_for_request(request_id: str) -> List[GenerationAuditEvent]:
    return sorted(
        [e for e in _audit if e.request_id == request_id],
        key=lambda e: e.timestamp,
    )


# ── Persistence ───────────────────────────────────────────────────────────────
def _dt(val) -> Optional[datetime]:
    if val is None:
        return None
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


def load() -> None:
    """Load all stores from gen_store.json."""
    global _requests, _documents, _audit, _counters
    if not _STORE_PATH.exists():
        logger.info("No generation store at %s -- starting fresh", _STORE_PATH)
        return
    try:
        raw = json.loads(_STORE_PATH.read_text(encoding="utf-8"))

        # Requests
        for d in raw.get("requests", {}).values():
            r = GenerationRequest(
                request_id=d["request_id"],
                document_type=DocumentType(d["document_type"]),
                applicant_user_id=d.get("applicant_user_id", ""),
                requested_by=d.get("requested_by", ""),
                issued_by=d.get("issued_by"),
                department_code=d.get("department_code"),
                fields=d.get("fields", {}),
                supporting_docs=[
                    SupportingDocument(
                        doc_ref_id=sd["doc_ref_id"],
                        doc_type=sd["doc_type"],
                        filename=sd["filename"],
                        verified=sd.get("verified", False),
                        verified_by=sd.get("verified_by"),
                        verified_at=_dt(sd.get("verified_at")),
                    )
                    for sd in d.get("supporting_docs", [])
                ],
                status=GenerationStatus(d.get("status", "pending")),
                rejection_reason=d.get("rejection_reason"),
                case_clear=d.get("case_clear", False),
                verification_passed=d.get("verification_passed", False),
                submitted_at=_dt(d.get("submitted_at")) or datetime.now(timezone.utc),
                approved_at=_dt(d.get("approved_at")),
                completed_at=_dt(d.get("completed_at")),
                updated_at=_dt(d.get("updated_at")) or datetime.now(timezone.utc),
            )
            _requests[r.request_id] = r

        # Documents
        for d in raw.get("documents", {}).values():
            doc = GeneratedDocument(
                doc_id=d["doc_id"],
                request_id=d.get("request_id", ""),
                document_type=DocumentType(d["document_type"]),
                document_number=d.get("document_number", ""),
                applicant_user_id=d.get("applicant_user_id", ""),
                applicant_name=d.get("applicant_name", ""),
                issued_by=d.get("issued_by", ""),
                department_code=d.get("department_code", ""),
                issued_at=_dt(d.get("issued_at")) or datetime.now(timezone.utc),
                valid_from=_dt(d.get("valid_from")),
                valid_until=_dt(d.get("valid_until")),
                signature_status=SignatureStatus(d.get("signature_status", "unsigned")),
                signature_hash=d.get("signature_hash", ""),
                signature_value=d.get("signature_value", ""),
                signed_by=d.get("signed_by"),
                signed_at=_dt(d.get("signed_at")),
                qr_verification_url=d.get("qr_verification_url", ""),
                qr_payload_hash=d.get("qr_payload_hash", ""),
                watermark_type=WatermarkType(d.get("watermark_type", "OFFICIAL")),
                pdf_path=d.get("pdf_path", ""),
                pdf_size_bytes=d.get("pdf_size_bytes", 0),
                status=GenerationStatus(d.get("status", "complete")),
                revoked=d.get("revoked", False),
                revoked_at=_dt(d.get("revoked_at")),
                revoked_by=d.get("revoked_by"),
                revoke_reason=d.get("revoke_reason"),
                fields=d.get("fields", {}),
                created_at=_dt(d.get("created_at")) or datetime.now(timezone.utc),
            )
            _documents[doc.doc_id] = doc

        # Audit
        for e in raw.get("audit", []):
            _audit.append(GenerationAuditEvent(
                event_id=e.get("event_id", str(__import__("uuid").uuid4())),
                request_id=e.get("request_id", ""),
                doc_id=e.get("doc_id"),
                actor_user_id=e.get("actor_user_id", ""),
                action=e.get("action", ""),
                detail=e.get("detail"),
                ip_address=e.get("ip_address", ""),
                timestamp=_dt(e.get("timestamp")) or datetime.now(timezone.utc),
            ))

        _counters = raw.get("counters", {})

        logger.info(
            "Generation store loaded: %d requests, %d documents",
            len(_requests), len(_documents),
        )
    except Exception as e:
        logger.error("Failed to load generation store: %s", e, exc_info=True)


def flush() -> None:
    """Persist all in-memory stores to gen_store.json."""
    try:
        import dataclasses

        def _ser(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            raise TypeError(f"Not serializable: {type(obj)}")

        payload = {
            "requests":  {rid: r.to_dict()    for rid, r  in _requests.items()},
            "documents": {did: d.to_dict()    for did, d  in _documents.items()},
            "audit":     [e.to_dict()          for e       in _audit[-1000:]],
            "counters":  _counters,
        }
        _STORE_PATH.write_text(
            json.dumps(payload, default=_ser, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Generation store flushed to %s", _STORE_PATH)
    except Exception as e:
        logger.error("Failed to flush generation store: %s", e, exc_info=True)
