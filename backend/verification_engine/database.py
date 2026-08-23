"""
verification_engine/database.py — Async SQLite repository for verification data.

Tables:
  - verification_results  — aggregated verification outcomes
  - verification_steps    — individual step results (immutable)
  - manual_reviews        — officer review requests and outcomes
  - verification_history  — complete immutable audit trail
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from verification_engine.models import (
    DepartmentType,
    ManualReviewRequest,
    ReviewStatus,
    TrustBadge,
    VerificationHistoryEntry,
    VerificationResult,
    VerificationStep,
    VerificationStepStatus,
)

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "verification.db"
)


class VerificationDatabase:
    """Async SQLite repository for verification data."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.environ.get("VERIFICATION_DB", _DEFAULT_DB_PATH)
        self._conn: Optional[aiosqlite.Connection] = None

    async def initialise(self) -> None:
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._create_tables()
        logger.info("VerificationDatabase initialised at %s", self.db_path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _create_tables(self) -> None:
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS verification_results (
                verification_id    TEXT PRIMARY KEY,
                document_id        TEXT NOT NULL,
                trust_badge        TEXT NOT NULL DEFAULT 'yellow',
                fraud_score        REAL NOT NULL DEFAULT 0.0,
                overall_confidence REAL NOT NULL DEFAULT 0.0,
                department         TEXT NOT NULL DEFAULT 'general',
                passed_count       INTEGER NOT NULL DEFAULT 0,
                failed_count       INTEGER NOT NULL DEFAULT 0,
                warning_count      INTEGER NOT NULL DEFAULT 0,
                skipped_count      INTEGER NOT NULL DEFAULT 0,
                needs_manual_review INTEGER NOT NULL DEFAULT 0,
                review_reason      TEXT NOT NULL DEFAULT '',
                started_at         TEXT NOT NULL,
                completed_at       TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_vr_doc ON verification_results(document_id);
            CREATE INDEX IF NOT EXISTS idx_vr_badge ON verification_results(trust_badge);

            CREATE TABLE IF NOT EXISTS verification_steps (
                step_id            TEXT PRIMARY KEY,
                verification_id    TEXT NOT NULL,
                step_name          TEXT NOT NULL,
                step_order         INTEGER NOT NULL DEFAULT 0,
                status             TEXT NOT NULL DEFAULT 'pending',
                confidence         REAL NOT NULL DEFAULT 0.0,
                evidence           TEXT NOT NULL DEFAULT '',
                timestamp          TEXT NOT NULL,
                officer            TEXT NOT NULL DEFAULT '',
                verification_source TEXT NOT NULL DEFAULT '',
                detail             TEXT NOT NULL DEFAULT '{}',
                duration_ms        INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (verification_id) REFERENCES verification_results(verification_id)
            );

            CREATE INDEX IF NOT EXISTS idx_vs_ver ON verification_steps(verification_id);

            CREATE TABLE IF NOT EXISTS manual_reviews (
                review_id          TEXT PRIMARY KEY,
                verification_id    TEXT NOT NULL,
                document_id        TEXT NOT NULL,
                reason             TEXT NOT NULL DEFAULT '',
                status             TEXT NOT NULL DEFAULT 'pending',
                assigned_to        TEXT NOT NULL DEFAULT '',
                reviewer_notes     TEXT NOT NULL DEFAULT '',
                reviewer_badge     TEXT,
                reviewed_by        TEXT NOT NULL DEFAULT '',
                reviewed_at        TEXT,
                created_at         TEXT NOT NULL,
                FOREIGN KEY (verification_id) REFERENCES verification_results(verification_id)
            );

            CREATE INDEX IF NOT EXISTS idx_mr_status ON manual_reviews(status);
            CREATE INDEX IF NOT EXISTS idx_mr_doc ON manual_reviews(document_id);

            CREATE TABLE IF NOT EXISTS verification_history (
                entry_id           TEXT PRIMARY KEY,
                verification_id    TEXT NOT NULL,
                document_id        TEXT NOT NULL,
                action             TEXT NOT NULL,
                trust_badge        TEXT,
                confidence         REAL NOT NULL DEFAULT 0.0,
                evidence           TEXT NOT NULL DEFAULT '',
                officer            TEXT NOT NULL DEFAULT '',
                verification_source TEXT NOT NULL DEFAULT '',
                detail             TEXT NOT NULL DEFAULT '{}',
                timestamp          TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_vh_doc ON verification_history(document_id);
            CREATE INDEX IF NOT EXISTS idx_vh_ver ON verification_history(verification_id);
        """)
        await self._conn.commit()

    # ── Verification Results ─────────────────────────────────────────────

    async def save_result(self, result: VerificationResult) -> None:
        await self._conn.execute(
            """INSERT OR REPLACE INTO verification_results (
                verification_id, document_id, trust_badge, fraud_score,
                overall_confidence, department, passed_count, failed_count,
                warning_count, skipped_count, needs_manual_review,
                review_reason, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.verification_id, result.document_id,
                result.trust_badge.value, result.fraud_score,
                result.overall_confidence, result.department.value,
                result.passed_count, result.failed_count,
                result.warning_count, result.skipped_count,
                int(result.needs_manual_review), result.review_reason,
                result.started_at.isoformat(),
                result.completed_at.isoformat() if result.completed_at else None,
            ),
        )
        await self._conn.commit()

    async def save_steps(self, steps: List[VerificationStep], verification_id: str) -> None:
        for step in steps:
            await self._conn.execute(
                """INSERT OR REPLACE INTO verification_steps (
                    step_id, verification_id, step_name, step_order,
                    status, confidence, evidence, timestamp, officer,
                    verification_source, detail, duration_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    step.step_id, verification_id, step.step_name,
                    step.step_order, step.status.value, step.confidence,
                    step.evidence, step.timestamp.isoformat(), step.officer,
                    step.verification_source, json.dumps(step.detail),
                    step.duration_ms,
                ),
            )
        await self._conn.commit()

    async def get_result(self, verification_id: str) -> Optional[VerificationResult]:
        cursor = await self._conn.execute(
            "SELECT * FROM verification_results WHERE verification_id = ?",
            (verification_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        # Load steps
        steps_cursor = await self._conn.execute(
            "SELECT * FROM verification_steps WHERE verification_id = ? ORDER BY step_order",
            (verification_id,),
        )
        step_rows = await steps_cursor.fetchall()
        steps = [
            VerificationStep(
                step_id=s["step_id"],
                step_name=s["step_name"],
                step_order=s["step_order"],
                status=VerificationStepStatus(s["status"]),
                confidence=s["confidence"],
                evidence=s["evidence"],
                timestamp=datetime.fromisoformat(s["timestamp"]),
                officer=s["officer"],
                verification_source=s["verification_source"],
                detail=json.loads(s["detail"]),
                duration_ms=s["duration_ms"],
            )
            for s in step_rows
        ]

        return VerificationResult(
            verification_id=row["verification_id"],
            document_id=row["document_id"],
            trust_badge=TrustBadge(row["trust_badge"]),
            fraud_score=row["fraud_score"],
            overall_confidence=row["overall_confidence"],
            department=DepartmentType(row["department"]),
            passed_count=row["passed_count"],
            failed_count=row["failed_count"],
            warning_count=row["warning_count"],
            skipped_count=row["skipped_count"],
            needs_manual_review=bool(row["needs_manual_review"]),
            review_reason=row["review_reason"],
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
            steps=steps,
        )

    async def get_results_for_document(self, document_id: str) -> List[VerificationResult]:
        cursor = await self._conn.execute(
            "SELECT verification_id FROM verification_results WHERE document_id = ? ORDER BY started_at DESC",
            (document_id,),
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            r = await self.get_result(row["verification_id"])
            if r:
                results.append(r)
        return results

    # ── Manual Reviews ───────────────────────────────────────────────────

    async def save_review(self, review: ManualReviewRequest) -> None:
        await self._conn.execute(
            """INSERT OR REPLACE INTO manual_reviews (
                review_id, verification_id, document_id, reason,
                status, assigned_to, reviewer_notes, reviewer_badge,
                reviewed_by, reviewed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                review.review_id, review.verification_id, review.document_id,
                review.reason, review.status.value, review.assigned_to,
                review.reviewer_notes,
                review.reviewer_badge.value if review.reviewer_badge else None,
                review.reviewed_by,
                review.reviewed_at.isoformat() if review.reviewed_at else None,
                review.created_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_review(self, review_id: str) -> Optional[ManualReviewRequest]:
        cursor = await self._conn.execute(
            "SELECT * FROM manual_reviews WHERE review_id = ?", (review_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return ManualReviewRequest(
            review_id=row["review_id"],
            verification_id=row["verification_id"],
            document_id=row["document_id"],
            reason=row["reason"],
            status=ReviewStatus(row["status"]),
            assigned_to=row["assigned_to"],
            reviewer_notes=row["reviewer_notes"],
            reviewer_badge=TrustBadge(row["reviewer_badge"]) if row["reviewer_badge"] else None,
            reviewed_by=row["reviewed_by"],
            reviewed_at=datetime.fromisoformat(row["reviewed_at"]) if row["reviewed_at"] else None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    async def list_reviews(self, status: Optional[str] = None, limit: int = 50) -> List[ManualReviewRequest]:
        if status:
            cursor = await self._conn.execute(
                "SELECT * FROM manual_reviews WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = await self._conn.execute(
                "SELECT * FROM manual_reviews ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [
            ManualReviewRequest(
                review_id=r["review_id"],
                verification_id=r["verification_id"],
                document_id=r["document_id"],
                reason=r["reason"],
                status=ReviewStatus(r["status"]),
                assigned_to=r["assigned_to"],
                reviewer_notes=r["reviewer_notes"],
                reviewer_badge=TrustBadge(r["reviewer_badge"]) if r["reviewer_badge"] else None,
                reviewed_by=r["reviewed_by"],
                reviewed_at=datetime.fromisoformat(r["reviewed_at"]) if r["reviewed_at"] else None,
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    # ── Verification History ─────────────────────────────────────────────

    async def log_history(self, entry: VerificationHistoryEntry) -> None:
        await self._conn.execute(
            """INSERT INTO verification_history (
                entry_id, verification_id, document_id, action,
                trust_badge, confidence, evidence, officer,
                verification_source, detail, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.entry_id, entry.verification_id, entry.document_id,
                entry.action,
                entry.trust_badge.value if entry.trust_badge else None,
                entry.confidence, entry.evidence, entry.officer,
                entry.verification_source, json.dumps(entry.detail),
                entry.timestamp.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_history(self, document_id: str, limit: int = 100) -> List[VerificationHistoryEntry]:
        cursor = await self._conn.execute(
            "SELECT * FROM verification_history WHERE document_id = ? ORDER BY timestamp DESC LIMIT ?",
            (document_id, limit),
        )
        rows = await cursor.fetchall()
        return [
            VerificationHistoryEntry(
                entry_id=r["entry_id"],
                verification_id=r["verification_id"],
                document_id=r["document_id"],
                action=r["action"],
                trust_badge=TrustBadge(r["trust_badge"]) if r["trust_badge"] else None,
                confidence=r["confidence"],
                evidence=r["evidence"],
                officer=r["officer"],
                verification_source=r["verification_source"],
                detail=json.loads(r["detail"]),
                timestamp=datetime.fromisoformat(r["timestamp"]),
            )
            for r in rows
        ]
