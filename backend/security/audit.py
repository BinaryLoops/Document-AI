"""
security/audit.py -- Audit Service & Chain-of-Custody.

Features:
  - Immutable audit log (SHA-256 hash chain)
  - SIEM-ready structured log entries
  - Chain-of-custody tracking for documents
  - Tamper detection via hash verification
  - Async SQLite persistence
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

logger = logging.getLogger(__name__)

_db: Optional[aiosqlite.Connection] = None


# ── Models ───────────────────────────────────────────────────────────────────

class AuditCategory:
    AUTH = "auth"
    DOCUMENT = "document"
    VERIFICATION = "verification"
    GENERATION = "generation"
    ACCESS = "access"
    ADMIN = "admin"
    SECURITY = "security"
    SYSTEM = "system"


class AuditSeverity:
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    ALERT = "alert"


@dataclass
class AuditEntry:
    """An immutable audit log entry with hash chain."""
    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    category: str = AuditCategory.SYSTEM
    severity: str = AuditSeverity.INFO
    action: str = ""
    actor_id: str = ""
    actor_name: str = ""
    actor_ip: str = ""
    resource_type: str = ""       # document, user, case, etc.
    resource_id: str = ""
    description: str = ""
    device_fingerprint: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    prev_hash: str = ""          # Hash of previous entry (chain)
    entry_hash: str = ""         # SHA-256 of this entry

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of this entry for tamper detection."""
        data = (
            f"{self.entry_id}|{self.timestamp}|{self.category}|{self.severity}|"
            f"{self.action}|{self.actor_id}|{self.resource_type}|{self.resource_id}|"
            f"{self.description}|{self.prev_hash}"
        )
        return hashlib.sha256(data.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp,
            "category": self.category,
            "severity": self.severity,
            "action": self.action,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "actor_ip": self.actor_ip,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "description": self.description,
            "device_fingerprint": self.device_fingerprint[:16] if self.device_fingerprint else "",
            "metadata": self.metadata,
            "entry_hash": self.entry_hash,
            "prev_hash": self.prev_hash,
        }

    def to_siem(self) -> Dict[str, Any]:
        """Export as SIEM-ready structured log (CEF-like)."""
        return {
            "event_id": self.entry_id,
            "event_time": self.timestamp,
            "event_category": self.category,
            "event_severity": self.severity,
            "event_action": self.action,
            "src_user": self.actor_id,
            "src_ip": self.actor_ip,
            "dst_type": self.resource_type,
            "dst_id": self.resource_id,
            "msg": self.description,
            "device_id": self.device_fingerprint[:16] if self.device_fingerprint else "",
            "integrity_hash": self.entry_hash,
        }


@dataclass
class CustodyEvent:
    """Chain-of-custody event for a document."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    action: str = ""             # created, accessed, modified, transferred, archived, deleted
    actor_id: str = ""
    actor_name: str = ""
    actor_role: str = ""
    from_department: str = ""
    to_department: str = ""
    notes: str = ""
    entry_hash: str = ""

    def compute_hash(self, prev_hash: str = "") -> str:
        data = f"{self.event_id}|{self.document_id}|{self.timestamp}|{self.action}|{self.actor_id}|{prev_hash}"
        self.entry_hash = hashlib.sha256(data.encode()).hexdigest()
        return self.entry_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "document_id": self.document_id,
            "timestamp": self.timestamp,
            "action": self.action,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "actor_role": self.actor_role,
            "from_department": self.from_department,
            "to_department": self.to_department,
            "notes": self.notes,
            "entry_hash": self.entry_hash,
        }


# ── Database ────────────────────────────────────────────────────────────────

async def init_audit_db(db_path: str = "audit.db") -> aiosqlite.Connection:
    """Initialize audit database."""
    global _db
    _db = await aiosqlite.connect(db_path)
    _db.row_factory = aiosqlite.Row

    await _db.executescript("""
        CREATE TABLE IF NOT EXISTS audit_log (
            entry_id          TEXT PRIMARY KEY,
            timestamp         TEXT NOT NULL,
            category          TEXT NOT NULL,
            severity          TEXT NOT NULL DEFAULT 'info',
            action            TEXT NOT NULL,
            actor_id          TEXT DEFAULT '',
            actor_name        TEXT DEFAULT '',
            actor_ip          TEXT DEFAULT '',
            resource_type     TEXT DEFAULT '',
            resource_id       TEXT DEFAULT '',
            description       TEXT DEFAULT '',
            device_fingerprint TEXT DEFAULT '',
            metadata_json     TEXT DEFAULT '{}',
            prev_hash         TEXT DEFAULT '',
            entry_hash        TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS custody_chain (
            event_id      TEXT PRIMARY KEY,
            document_id   TEXT NOT NULL,
            timestamp     TEXT NOT NULL,
            action        TEXT NOT NULL,
            actor_id      TEXT DEFAULT '',
            actor_name    TEXT DEFAULT '',
            actor_role    TEXT DEFAULT '',
            from_dept     TEXT DEFAULT '',
            to_dept       TEXT DEFAULT '',
            notes         TEXT DEFAULT '',
            entry_hash    TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_audit_time     ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_category  ON audit_log(category);
        CREATE INDEX IF NOT EXISTS idx_audit_severity  ON audit_log(severity);
        CREATE INDEX IF NOT EXISTS idx_audit_actor     ON audit_log(actor_id);
        CREATE INDEX IF NOT EXISTS idx_audit_resource  ON audit_log(resource_type, resource_id);
        CREATE INDEX IF NOT EXISTS idx_custody_doc     ON custody_chain(document_id);
    """)

    await _db.commit()
    logger.info("Audit database initialized: %s", db_path)
    return _db


async def close_audit_db():
    global _db
    if _db:
        await _db.close()
        _db = None


def _get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Audit database not initialized")
    return _db


# ── Audit Service ───────────────────────────────────────────────────────────

_last_hash = ""  # In-memory hash chain head


async def log_audit(
    action: str,
    category: str = AuditCategory.SYSTEM,
    severity: str = AuditSeverity.INFO,
    actor_id: str = "",
    actor_name: str = "",
    actor_ip: str = "",
    resource_type: str = "",
    resource_id: str = "",
    description: str = "",
    device_fingerprint: str = "",
    metadata: Optional[Dict] = None,
) -> AuditEntry:
    """Log an immutable audit entry with hash chain."""
    global _last_hash
    db = _get_db()

    entry = AuditEntry(
        category=category,
        severity=severity,
        action=action,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_ip=actor_ip,
        resource_type=resource_type,
        resource_id=resource_id,
        description=description,
        device_fingerprint=device_fingerprint,
        metadata=metadata or {},
        prev_hash=_last_hash,
    )
    entry.entry_hash = entry.compute_hash()
    _last_hash = entry.entry_hash

    await db.execute(
        """INSERT INTO audit_log
           (entry_id, timestamp, category, severity, action, actor_id, actor_name,
            actor_ip, resource_type, resource_id, description, device_fingerprint,
            metadata_json, prev_hash, entry_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            entry.entry_id, entry.timestamp, entry.category, entry.severity,
            entry.action, entry.actor_id, entry.actor_name, entry.actor_ip,
            entry.resource_type, entry.resource_id, entry.description,
            entry.device_fingerprint, json.dumps(entry.metadata),
            entry.prev_hash, entry.entry_hash,
        ),
    )
    await db.commit()
    return entry


async def get_audit_log(
    category: Optional[str] = None,
    severity: Optional[str] = None,
    actor_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[AuditEntry]:
    """Query audit log with filters."""
    db = _get_db()
    query = "SELECT * FROM audit_log WHERE 1=1"
    params: list = []

    if category:
        query += " AND category = ?"
        params.append(category)
    if severity:
        query += " AND severity = ?"
        params.append(severity)
    if actor_id:
        query += " AND actor_id = ?"
        params.append(actor_id)
    if resource_type:
        query += " AND resource_type = ?"
        params.append(resource_type)
    if resource_id:
        query += " AND resource_id = ?"
        params.append(resource_id)

    query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [_row_to_audit(r) for r in rows]


async def verify_audit_chain(limit: int = 1000) -> Dict[str, Any]:
    """Verify the integrity of the audit hash chain (tamper detection)."""
    db = _get_db()
    cursor = await db.execute(
        "SELECT * FROM audit_log ORDER BY timestamp ASC LIMIT ?", (limit,)
    )
    rows = await cursor.fetchall()

    total = len(rows)
    valid = 0
    tampered = []

    prev_hash = ""
    for row in rows:
        entry = _row_to_audit(row)
        expected = entry.compute_hash()

        if entry.entry_hash != expected:
            tampered.append({"entry_id": entry.entry_id, "reason": "hash_mismatch"})
        elif entry.prev_hash != prev_hash:
            tampered.append({"entry_id": entry.entry_id, "reason": "chain_break"})
        else:
            valid += 1

        prev_hash = entry.entry_hash

    return {
        "total_entries": total,
        "valid_entries": valid,
        "tampered_entries": len(tampered),
        "integrity": "intact" if not tampered else "compromised",
        "tampered_details": tampered[:20],
    }


# ── Chain of Custody ────────────────────────────────────────────────────────

async def add_custody_event(
    document_id: str,
    action: str,
    actor_id: str = "",
    actor_name: str = "",
    actor_role: str = "",
    from_department: str = "",
    to_department: str = "",
    notes: str = "",
) -> CustodyEvent:
    """Add a chain-of-custody event for a document."""
    db = _get_db()

    # Get last hash for this document
    cursor = await db.execute(
        "SELECT entry_hash FROM custody_chain WHERE document_id = ? ORDER BY timestamp DESC LIMIT 1",
        (document_id,),
    )
    row = await cursor.fetchone()
    prev_hash = row["entry_hash"] if row else ""

    event = CustodyEvent(
        document_id=document_id,
        action=action,
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        from_department=from_department,
        to_department=to_department,
        notes=notes,
    )
    event.compute_hash(prev_hash)

    await db.execute(
        """INSERT INTO custody_chain
           (event_id, document_id, timestamp, action, actor_id, actor_name,
            actor_role, from_dept, to_dept, notes, entry_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event.event_id, event.document_id, event.timestamp, event.action,
            event.actor_id, event.actor_name, event.actor_role,
            event.from_department, event.to_department, event.notes,
            event.entry_hash,
        ),
    )
    await db.commit()

    # Also log to audit
    await log_audit(
        action=f"custody_{action}",
        category=AuditCategory.DOCUMENT,
        actor_id=actor_id,
        resource_type="document",
        resource_id=document_id,
        description=f"Custody: {action} by {actor_name or actor_id}",
    )

    return event


async def get_custody_chain(document_id: str) -> List[CustodyEvent]:
    """Get the full chain-of-custody for a document."""
    db = _get_db()
    cursor = await db.execute(
        "SELECT * FROM custody_chain WHERE document_id = ? ORDER BY timestamp ASC",
        (document_id,),
    )
    rows = await cursor.fetchall()
    return [_row_to_custody(r) for r in rows]


# ── Helpers ─────────────────────────────────────────────────────────────────

def _row_to_audit(row) -> AuditEntry:
    return AuditEntry(
        entry_id=row["entry_id"],
        timestamp=row["timestamp"],
        category=row["category"],
        severity=row["severity"],
        action=row["action"],
        actor_id=row["actor_id"],
        actor_name=row["actor_name"],
        actor_ip=row["actor_ip"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        description=row["description"],
        device_fingerprint=row["device_fingerprint"],
        metadata=json.loads(row["metadata_json"] or "{}"),
        prev_hash=row["prev_hash"],
        entry_hash=row["entry_hash"],
    )


def _row_to_custody(row) -> CustodyEvent:
    return CustodyEvent(
        event_id=row["event_id"],
        document_id=row["document_id"],
        timestamp=row["timestamp"],
        action=row["action"],
        actor_id=row["actor_id"],
        actor_name=row["actor_name"],
        actor_role=row["actor_role"],
        from_department=row["from_dept"],
        to_department=row["to_dept"],
        notes=row["notes"],
        entry_hash=row["entry_hash"],
    )
