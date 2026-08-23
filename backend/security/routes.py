"""
security/routes.py -- FastAPI endpoints for Enterprise Security.

Endpoints:
  GET  /security/audit          — Query audit log
  GET  /security/audit/verify   — Verify audit chain integrity (tamper detection)
  GET  /security/events         — Get security incidents
  GET  /security/anomalies      — Get anomaly detection results
  GET  /security/custody/{id}   — Get chain-of-custody for a document
  POST /security/consent        — Grant user consent
  DELETE /security/consent      — Revoke consent
  GET  /security/consent/{uid}  — Get user consents
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from security.audit import (
    AuditCategory,
    AuditSeverity,
    get_audit_log,
    get_custody_chain,
    verify_audit_chain,
)
from security.incidents import IncidentDetector

logger = logging.getLogger(__name__)


# ── Request models ───────────────────────────────────────────────────────────

class ConsentRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    consent_type: str = Field(..., description="Type: data_processing, sharing, storage, analytics")
    purpose: str = Field("", description="Purpose of consent")
    ip_address: str = Field("", description="IP address of user")


class ConsentRevokeRequest(BaseModel):
    user_id: str = Field(..., description="User ID")
    consent_type: str = Field(..., description="Consent type to revoke")


# ── Router factory ───────────────────────────────────────────────────────────

def create_security_router(detector: IncidentDetector) -> APIRouter:
    """Create and return the security API router."""

    router = APIRouter(prefix="/security", tags=["Security"])

    # ── GET /security/audit ──────────────────────────────────────────────

    @router.get("/audit", summary="Query audit log")
    async def query_audit(
        category: Optional[str] = Query(None, description="Filter by category (auth, document, security, etc.)"),
        severity: Optional[str] = Query(None, description="Filter by severity (info, warning, critical, alert)"),
        actor_id: Optional[str] = Query(None, description="Filter by actor user ID"),
        resource_type: Optional[str] = Query(None, description="Filter by resource type"),
        resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
        limit: int = Query(100, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        siem_format: bool = Query(False, description="Return in SIEM-ready format"),
    ) -> Dict[str, Any]:
        """
        Query the immutable audit log.

        Each entry includes:
        - SHA-256 hash (tamper detection)
        - Previous entry hash (chain integrity)
        - SIEM-ready export format

        Categories: auth, document, verification, generation, access, admin, security, system
        """
        entries = await get_audit_log(
            category=category,
            severity=severity,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
            offset=offset,
        )

        if siem_format:
            return {
                "status": "success",
                "entries": [e.to_siem() for e in entries],
                "count": len(entries),
                "format": "SIEM",
            }

        return {
            "status": "success",
            "entries": [e.to_dict() for e in entries],
            "count": len(entries),
        }

    # ── GET /security/audit/verify ───────────────────────────────────────

    @router.get("/audit/verify", summary="Verify audit chain integrity")
    async def verify_chain(
        limit: int = Query(1000, ge=1, le=10000),
    ) -> Dict[str, Any]:
        """
        Verify the integrity of the audit hash chain.

        Checks:
        - Each entry's hash matches its content (tamper detection)
        - Each entry's prev_hash matches the previous entry's hash (chain continuity)

        Returns: integrity status (intact/compromised) with details.
        """
        result = await verify_audit_chain(limit)
        return {"status": "success", "verification": result}

    # ── GET /security/events ─────────────────────────────────────────────

    @router.get("/events", summary="Get security incidents")
    async def get_events(
        incident_type: Optional[str] = Query(None, description="Filter by type"),
        severity: Optional[str] = Query(None, description="Filter by severity"),
        status: Optional[str] = Query(None, description="Filter by status"),
        limit: int = Query(50, ge=1, le=200),
    ) -> Dict[str, Any]:
        """
        Get security incidents detected by the system.

        Types: suspicious_login, brute_force, device_change, geo_anomaly,
               excessive_access, off_hours_access, privilege_escalation,
               data_exfiltration, tamper_detected, malware_detected
        """
        incidents = detector.get_incidents(
            incident_type=incident_type,
            severity=severity,
            status=status,
            limit=limit,
        )

        return {
            "status": "success",
            "incidents": [i.to_dict() for i in incidents],
            "count": len(incidents),
        }

    # ── GET /security/anomalies ──────────────────────────────────────────

    @router.get("/anomalies", summary="Get anomaly detection results")
    async def get_anomalies() -> Dict[str, Any]:
        """
        Get current anomaly scores for all tracked users.

        Score 0.0 = normal, 1.0 = highly anomalous.
        Recommendation: allow / monitor / block.

        Factors checked:
        - Excessive access rate
        - Off-hours access
        - Unknown IP addresses
        """
        anomalies = detector.get_anomalies()
        return {
            "status": "success",
            "anomalies": anomalies,
            "count": len(anomalies),
        }

    # ── GET /security/custody/{id} ───────────────────────────────────────

    @router.get("/custody/{document_id}", summary="Get chain-of-custody")
    async def get_custody(document_id: str) -> Dict[str, Any]:
        """
        Get the full chain-of-custody for a document.

        Each event is hash-chained for immutability.
        Shows who handled the document, when, and what they did.
        """
        chain = await get_custody_chain(document_id)
        return {
            "status": "success",
            "document_id": document_id,
            "custody_chain": [e.to_dict() for e in chain],
            "event_count": len(chain),
        }

    # ── POST /security/consent ───────────────────────────────────────────

    @router.post("/consent", summary="Grant user consent")
    async def grant_consent(body: ConsentRequest) -> Dict[str, Any]:
        """
        Record user consent for data processing.

        Types: data_processing, sharing, storage, analytics
        """
        record = detector.grant_consent(
            user_id=body.user_id,
            consent_type=body.consent_type,
            purpose=body.purpose,
            ip_address=body.ip_address,
        )
        return {
            "status": "success",
            "consent": record.to_dict(),
        }

    # ── DELETE /security/consent ─────────────────────────────────────────

    @router.delete("/consent", summary="Revoke user consent")
    async def revoke_consent(body: ConsentRevokeRequest) -> Dict[str, Any]:
        """Revoke a user's consent."""
        record = detector.revoke_consent(body.user_id, body.consent_type)
        if not record:
            raise HTTPException(404, f"No active consent found for type: {body.consent_type}")
        return {
            "status": "success",
            "consent": record.to_dict(),
        }

    # ── GET /security/consent/{uid} ──────────────────────────────────────

    @router.get("/consent/{user_id}", summary="Get user consents")
    async def get_consents(user_id: str) -> Dict[str, Any]:
        """Get all consent records for a user."""
        consents = detector.get_consents(user_id)
        return {
            "status": "success",
            "consents": [c.to_dict() for c in consents],
            "count": len(consents),
        }

    return router
