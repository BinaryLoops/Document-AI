"""
security/incidents.py -- Incident Detection Service.

Features:
  - Suspicious login detection (geo anomaly, device change, brute force)
  - Anomaly detection (usage patterns, access patterns)
  - Security event classification
  - Incident management (create, escalate, resolve)
  - Consent management
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── Models ───────────────────────────────────────────────────────────────────

class IncidentSeverity:
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus:
    OPEN = "open"
    INVESTIGATING = "investigating"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


class IncidentType:
    SUSPICIOUS_LOGIN = "suspicious_login"
    BRUTE_FORCE = "brute_force"
    DEVICE_CHANGE = "device_change"
    GEO_ANOMALY = "geo_anomaly"
    EXCESSIVE_ACCESS = "excessive_access"
    OFF_HOURS_ACCESS = "off_hours_access"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    TAMPER_DETECTED = "tamper_detected"
    MALWARE_DETECTED = "malware_detected"


@dataclass
class SecurityIncident:
    """A security incident requiring investigation."""
    incident_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    incident_type: str = ""
    severity: str = IncidentSeverity.MEDIUM
    status: str = IncidentStatus.OPEN
    title: str = ""
    description: str = ""
    actor_id: str = ""
    actor_ip: str = ""
    device_fingerprint: str = ""
    resource_type: str = ""
    resource_id: str = ""
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: str = ""
    resolved_by: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "type": self.incident_type,
            "severity": self.severity,
            "status": self.status,
            "title": self.title,
            "description": self.description,
            "actor_id": self.actor_id,
            "actor_ip": self.actor_ip,
            "device_fingerprint": self.device_fingerprint[:16] if self.device_fingerprint else "",
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "evidence": self.evidence[:10],
            "created_at": self.created_at,
            "status": self.status,
        }


@dataclass
class AnomalyScore:
    """Anomaly detection result."""
    user_id: str = ""
    score: float = 0.0         # 0=normal, 1=highly anomalous
    factors: List[Dict[str, Any]] = field(default_factory=list)
    recommendation: str = ""   # allow, monitor, block

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "anomaly_score": round(self.score, 3),
            "factors": self.factors,
            "recommendation": self.recommendation,
        }


@dataclass
class ConsentRecord:
    """User consent record."""
    consent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    consent_type: str = ""     # data_processing, sharing, storage, analytics
    granted: bool = False
    granted_at: str = ""
    revoked_at: str = ""
    ip_address: str = ""
    purpose: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "consent_id": self.consent_id,
            "user_id": self.user_id,
            "consent_type": self.consent_type,
            "granted": self.granted,
            "granted_at": self.granted_at,
            "revoked_at": self.revoked_at,
            "purpose": self.purpose,
        }


# ── Incident Detection Engine ──────────────────────────────────────────────

class IncidentDetector:
    """
    Detects security incidents from login and access patterns.

    Tracks:
      - Failed login attempts (brute force detection)
      - Device fingerprint changes
      - Geographic anomalies (IP-based)
      - Off-hours access patterns
      - Excessive resource access rates
    """

    def __init__(
        self,
        max_failed_logins: int = 5,
        failed_login_window: int = 300,    # seconds
        max_access_per_minute: int = 30,
    ):
        self.max_failed_logins = max_failed_logins
        self.failed_login_window = failed_login_window
        self.max_access_per_minute = max_access_per_minute

        # In-memory tracking
        self._failed_logins: Dict[str, List[float]] = defaultdict(list)  # user -> timestamps
        self._known_devices: Dict[str, Set[str]] = defaultdict(set)      # user -> fingerprints
        self._known_ips: Dict[str, Set[str]] = defaultdict(set)          # user -> IPs
        self._access_counts: Dict[str, List[float]] = defaultdict(list)  # user -> timestamps
        self._incidents: List[SecurityIncident] = []
        self._consents: Dict[str, List[ConsentRecord]] = defaultdict(list)

    # ── Login Analysis ───────────────────────────────────────────────────

    def analyze_login(
        self,
        user_id: str,
        ip_address: str,
        device_fingerprint: str = "",
        success: bool = True,
        user_agent: str = "",
    ) -> List[SecurityIncident]:
        """
        Analyze a login attempt and return any detected incidents.
        """
        incidents = []
        now = time.time()

        if not success:
            # Track failed attempt
            self._failed_logins[user_id].append(now)
            # Clean old entries
            self._failed_logins[user_id] = [
                t for t in self._failed_logins[user_id]
                if now - t < self.failed_login_window
            ]
            # Check brute force
            if len(self._failed_logins[user_id]) >= self.max_failed_logins:
                incident = SecurityIncident(
                    incident_type=IncidentType.BRUTE_FORCE,
                    severity=IncidentSeverity.HIGH,
                    title=f"Brute force detected: {user_id}",
                    description=f"{len(self._failed_logins[user_id])} failed login attempts in {self.failed_login_window}s",
                    actor_id=user_id,
                    actor_ip=ip_address,
                    device_fingerprint=device_fingerprint,
                    evidence=[
                        {"type": "failed_attempts", "count": len(self._failed_logins[user_id])},
                        {"type": "window_seconds", "value": self.failed_login_window},
                    ],
                )
                incidents.append(incident)
                self._incidents.append(incident)
            return incidents

        # Successful login — check for anomalies
        self._failed_logins[user_id] = []  # Reset failed count

        # Device change detection
        if device_fingerprint and self._known_devices[user_id]:
            if device_fingerprint not in self._known_devices[user_id]:
                incident = SecurityIncident(
                    incident_type=IncidentType.DEVICE_CHANGE,
                    severity=IncidentSeverity.MEDIUM,
                    title=f"New device detected for {user_id}",
                    description=f"Login from unknown device. Known: {len(self._known_devices[user_id])}, New: {device_fingerprint[:16]}",
                    actor_id=user_id,
                    actor_ip=ip_address,
                    device_fingerprint=device_fingerprint,
                    evidence=[
                        {"type": "known_devices", "count": len(self._known_devices[user_id])},
                        {"type": "new_fingerprint", "value": device_fingerprint[:16]},
                    ],
                )
                incidents.append(incident)
                self._incidents.append(incident)

        self._known_devices[user_id].add(device_fingerprint)

        # IP anomaly detection
        if ip_address and self._known_ips[user_id]:
            if ip_address not in self._known_ips[user_id]:
                # Check if subnet is different (simple /16 check)
                known_subnets = {ip.rsplit(".", 2)[0] for ip in self._known_ips[user_id] if "." in ip}
                new_subnet = ip_address.rsplit(".", 2)[0] if "." in ip_address else ""
                if new_subnet and new_subnet not in known_subnets:
                    incident = SecurityIncident(
                        incident_type=IncidentType.GEO_ANOMALY,
                        severity=IncidentSeverity.MEDIUM,
                        title=f"Suspicious login location for {user_id}",
                        description=f"Login from new network: {ip_address}",
                        actor_id=user_id,
                        actor_ip=ip_address,
                        evidence=[
                            {"type": "known_ips", "count": len(self._known_ips[user_id])},
                            {"type": "new_ip", "value": ip_address},
                        ],
                    )
                    incidents.append(incident)
                    self._incidents.append(incident)

        self._known_ips[user_id].add(ip_address)

        return incidents

    # ── Anomaly Detection ────────────────────────────────────────────────

    def analyze_access(
        self,
        user_id: str,
        resource_type: str = "",
        resource_id: str = "",
        ip_address: str = "",
    ) -> AnomalyScore:
        """
        Analyze a resource access for anomalies.
        Returns an anomaly score.
        """
        now = time.time()
        factors = []
        score = 0.0

        # Track access rate
        self._access_counts[user_id].append(now)
        self._access_counts[user_id] = [
            t for t in self._access_counts[user_id] if now - t < 60
        ]

        # Excessive access rate
        rate = len(self._access_counts[user_id])
        if rate > self.max_access_per_minute:
            score += 0.4
            factors.append({
                "type": "excessive_access_rate",
                "rate_per_minute": rate,
                "threshold": self.max_access_per_minute,
            })

        # Off-hours access (outside 8AM-8PM UTC)
        hour = datetime.now(timezone.utc).hour
        if hour < 8 or hour > 20:
            score += 0.15
            factors.append({
                "type": "off_hours_access",
                "hour_utc": hour,
            })

        # Unknown IP
        if ip_address and ip_address not in self._known_ips.get(user_id, set()):
            score += 0.1
            factors.append({"type": "unknown_ip", "ip": ip_address})

        score = min(score, 1.0)
        recommendation = "allow" if score < 0.3 else ("monitor" if score < 0.6 else "block")

        return AnomalyScore(
            user_id=user_id,
            score=score,
            factors=factors,
            recommendation=recommendation,
        )

    # ── Incident Management ──────────────────────────────────────────────

    def get_incidents(
        self,
        incident_type: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[SecurityIncident]:
        """Get security incidents with optional filters."""
        results = self._incidents

        if incident_type:
            results = [i for i in results if i.incident_type == incident_type]
        if severity:
            results = [i for i in results if i.severity == severity]
        if status:
            results = [i for i in results if i.status == status]

        return sorted(results, key=lambda i: i.created_at, reverse=True)[:limit]

    def get_anomalies(self) -> List[Dict[str, Any]]:
        """Get current anomaly scores for all tracked users."""
        anomalies = []
        for user_id in self._access_counts:
            score = self.analyze_access(user_id)
            if score.score > 0.1:
                anomalies.append(score.to_dict())
        return sorted(anomalies, key=lambda a: a["anomaly_score"], reverse=True)

    # ── Consent Management ───────────────────────────────────────────────

    def grant_consent(
        self,
        user_id: str,
        consent_type: str,
        purpose: str = "",
        ip_address: str = "",
    ) -> ConsentRecord:
        """Record user consent."""
        record = ConsentRecord(
            user_id=user_id,
            consent_type=consent_type,
            granted=True,
            granted_at=datetime.now(timezone.utc).isoformat(),
            ip_address=ip_address,
            purpose=purpose,
        )
        self._consents[user_id].append(record)
        logger.info("Consent granted: user=%s type=%s", user_id, consent_type)
        return record

    def revoke_consent(
        self,
        user_id: str,
        consent_type: str,
    ) -> Optional[ConsentRecord]:
        """Revoke user consent."""
        for record in reversed(self._consents.get(user_id, [])):
            if record.consent_type == consent_type and record.granted:
                record.granted = False
                record.revoked_at = datetime.now(timezone.utc).isoformat()
                logger.info("Consent revoked: user=%s type=%s", user_id, consent_type)
                return record
        return None

    def get_consents(self, user_id: str) -> List[ConsentRecord]:
        """Get all consent records for a user."""
        return self._consents.get(user_id, [])

    def check_consent(self, user_id: str, consent_type: str) -> bool:
        """Check if a user has active consent for a type."""
        for record in reversed(self._consents.get(user_id, [])):
            if record.consent_type == consent_type:
                return record.granted
        return False
