"""
digilocker/database.py — Async SQLite repository for Digital Locker metadata.

Tables:
  - documents           — primary document metadata (all LockerDocument fields)
  - document_versions   — immutable version history (INSERT only)
  - deletion_requests   — controlled deletion workflow
  - audit_log           — every action logged

Design:
  - Async via aiosqlite for non-blocking I/O inside FastAPI.
  - Repository pattern — all SQL is encapsulated here.
  - Immutable records: document_versions and audit_log are INSERT-only.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from digilocker.models import (
    AuditAction,
    AuditRecord,
    DeletionRequest,
    DeletionStatus,
    DocumentCategory,
    DocumentLifecycle,
    DocumentVersion,
    LockerDocument,
    VerificationStatus,
)

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "digilocker.db"
)


class DocumentDatabase:
    """
    Async SQLite repository for Digital Locker documents.

    Usage::

        db = DocumentDatabase()
        await db.initialise()
        await db.insert_document(doc)
        doc = await db.get_document("uuid")
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.environ.get("DIGILOCKER_DB", _DEFAULT_DB_PATH)
        self._conn: Optional[aiosqlite.Connection] = None

    async def initialise(self) -> None:
        """Create tables if they don't exist."""
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._create_tables()
        logger.info("DocumentDatabase initialised at %s", self.db_path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ── Schema ───────────────────────────────────────────────────────────

    async def _create_tables(self) -> None:
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS documents (
                document_id        TEXT PRIMARY KEY,
                owner              TEXT NOT NULL,
                department         TEXT NOT NULL DEFAULT '',
                document_type      TEXT NOT NULL DEFAULT 'other',
                case_type          TEXT NOT NULL DEFAULT '',
                serial_number      TEXT NOT NULL DEFAULT '',
                qr_code            TEXT NOT NULL DEFAULT '',
                verification_status TEXT NOT NULL DEFAULT 'pending',
                confidence_score   REAL NOT NULL DEFAULT 0.0,
                file_hash          TEXT NOT NULL DEFAULT '',
                encryption_ref     TEXT NOT NULL DEFAULT '',
                original_filename  TEXT NOT NULL DEFAULT '',
                file_size          INTEGER NOT NULL DEFAULT 0,
                mime_type          TEXT NOT NULL DEFAULT '',
                page_count         INTEGER NOT NULL DEFAULT 0,
                ocr_text           TEXT NOT NULL DEFAULT '',
                extracted_metadata TEXT NOT NULL DEFAULT '{}',
                is_duplicate       INTEGER NOT NULL DEFAULT 0,
                duplicate_of       TEXT,
                preview_ref        TEXT NOT NULL DEFAULT '',
                thumbnail_ref      TEXT NOT NULL DEFAULT '',
                lifecycle          TEXT NOT NULL DEFAULT 'processing',
                version            INTEGER NOT NULL DEFAULT 1,
                perceptual_hash    TEXT,
                upload_timestamp   TEXT NOT NULL,
                updated_at         TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_doc_owner       ON documents(owner);
            CREATE INDEX IF NOT EXISTS idx_doc_type         ON documents(document_type);
            CREATE INDEX IF NOT EXISTS idx_doc_serial       ON documents(serial_number);
            CREATE INDEX IF NOT EXISTS idx_doc_hash         ON documents(file_hash);
            CREATE INDEX IF NOT EXISTS idx_doc_lifecycle    ON documents(lifecycle);
            CREATE INDEX IF NOT EXISTS idx_doc_department   ON documents(department);
            CREATE INDEX IF NOT EXISTS idx_doc_phash        ON documents(perceptual_hash);

            CREATE TABLE IF NOT EXISTS document_versions (
                version_id     TEXT PRIMARY KEY,
                document_id    TEXT NOT NULL,
                version        INTEGER NOT NULL,
                file_hash      TEXT NOT NULL DEFAULT '',
                encryption_ref TEXT NOT NULL DEFAULT '',
                file_size      INTEGER NOT NULL DEFAULT 0,
                change_summary TEXT NOT NULL DEFAULT '',
                created_by     TEXT NOT NULL DEFAULT '',
                created_at     TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(document_id)
            );

            CREATE INDEX IF NOT EXISTS idx_ver_doc ON document_versions(document_id);

            CREATE TABLE IF NOT EXISTS deletion_requests (
                request_id    TEXT PRIMARY KEY,
                document_id   TEXT NOT NULL,
                requested_by  TEXT NOT NULL,
                reason        TEXT NOT NULL DEFAULT '',
                status        TEXT NOT NULL DEFAULT 'pending',
                approved_by   TEXT,
                reviewed_at   TEXT,
                created_at    TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(document_id)
            );

            CREATE INDEX IF NOT EXISTS idx_del_status ON deletion_requests(status);
            CREATE INDEX IF NOT EXISTS idx_del_doc    ON deletion_requests(document_id);

            CREATE TABLE IF NOT EXISTS audit_log (
                audit_id     TEXT PRIMARY KEY,
                document_id  TEXT NOT NULL DEFAULT '',
                user_id      TEXT NOT NULL DEFAULT '',
                action       TEXT NOT NULL,
                detail       TEXT NOT NULL DEFAULT '',
                ip_address   TEXT NOT NULL DEFAULT '',
                timestamp    TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_audit_doc  ON audit_log(document_id);
            CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
        """)
        await self._conn.commit()

    # ── Document CRUD ────────────────────────────────────────────────────

    async def insert_document(self, doc: LockerDocument) -> None:
        """Insert a new document record."""
        await self._conn.execute(
            """INSERT INTO documents (
                document_id, owner, department, document_type, case_type,
                serial_number, qr_code, verification_status, confidence_score,
                file_hash, encryption_ref, original_filename, file_size,
                mime_type, page_count, ocr_text, extracted_metadata,
                is_duplicate, duplicate_of, preview_ref, thumbnail_ref,
                lifecycle, version, perceptual_hash, upload_timestamp, updated_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )""",
            (
                doc.document_id, doc.owner, doc.department,
                doc.document_type.value, doc.case_type, doc.serial_number,
                doc.qr_code, doc.verification_status.value, doc.confidence_score,
                doc.file_hash, doc.encryption_ref, doc.original_filename,
                doc.file_size, doc.mime_type, doc.page_count,
                doc.ocr_text, json.dumps(doc.extracted_metadata),
                int(doc.is_duplicate), doc.duplicate_of,
                doc.preview_ref, doc.thumbnail_ref,
                doc.lifecycle.value, doc.version,
                doc.extracted_metadata.get("perceptual_hash"),
                doc.upload_timestamp.isoformat(), doc.updated_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_document(self, document_id: str) -> Optional[LockerDocument]:
        """Fetch a single document by ID."""
        cursor = await self._conn.execute(
            "SELECT * FROM documents WHERE document_id = ?", (document_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_doc(row) if row else None

    async def list_documents(
        self,
        owner: Optional[str] = None,
        document_type: Optional[str] = None,
        department: Optional[str] = None,
        lifecycle: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[LockerDocument]:
        """List documents with optional filters and pagination."""
        clauses = ["lifecycle != 'deleted'"]
        params: list = []

        if owner:
            clauses.append("owner = ?")
            params.append(owner)
        if document_type:
            clauses.append("document_type = ?")
            params.append(document_type)
        if department:
            clauses.append("department = ?")
            params.append(department)
        if lifecycle:
            clauses.append("lifecycle = ?")
            params.append(lifecycle)

        where = " AND ".join(clauses)
        params.extend([limit, offset])

        cursor = await self._conn.execute(
            f"SELECT * FROM documents WHERE {where} "
            f"ORDER BY upload_timestamp DESC LIMIT ? OFFSET ?",
            params,
        )
        rows = await cursor.fetchall()
        return [self._row_to_doc(r) for r in rows]

    async def count_documents(
        self,
        owner: Optional[str] = None,
        document_type: Optional[str] = None,
        department: Optional[str] = None,
        lifecycle: Optional[str] = None,
    ) -> int:
        """Count documents matching filters."""
        clauses = ["lifecycle != 'deleted'"]
        params: list = []

        if owner:
            clauses.append("owner = ?")
            params.append(owner)
        if document_type:
            clauses.append("document_type = ?")
            params.append(document_type)
        if department:
            clauses.append("department = ?")
            params.append(department)
        if lifecycle:
            clauses.append("lifecycle = ?")
            params.append(lifecycle)

        where = " AND ".join(clauses)
        cursor = await self._conn.execute(
            f"SELECT COUNT(*) FROM documents WHERE {where}", params
        )
        row = await cursor.fetchone()
        return row[0]

    async def search_documents(
        self,
        query: Optional[str] = None,
        owner: Optional[str] = None,
        department: Optional[str] = None,
        document_type: Optional[str] = None,
        serial_number: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[LockerDocument]:
        """Full-text search across document metadata."""
        clauses = ["lifecycle != 'deleted'"]
        params: list = []

        if query:
            clauses.append(
                "(original_filename LIKE ? OR ocr_text LIKE ? "
                "OR serial_number LIKE ? OR department LIKE ?)"
            )
            q = f"%{query}%"
            params.extend([q, q, q, q])
        if owner:
            clauses.append("owner = ?")
            params.append(owner)
        if department:
            clauses.append("department = ?")
            params.append(department)
        if document_type:
            clauses.append("document_type = ?")
            params.append(document_type)
        if serial_number:
            clauses.append("serial_number LIKE ?")
            params.append(f"%{serial_number}%")
        if date_from:
            clauses.append("upload_timestamp >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("upload_timestamp <= ?")
            params.append(date_to)

        where = " AND ".join(clauses)
        params.extend([limit, offset])

        cursor = await self._conn.execute(
            f"SELECT * FROM documents WHERE {where} "
            f"ORDER BY upload_timestamp DESC LIMIT ? OFFSET ?",
            params,
        )
        rows = await cursor.fetchall()
        return [self._row_to_doc(r) for r in rows]

    async def update_lifecycle(
        self, document_id: str, lifecycle: DocumentLifecycle
    ) -> None:
        """Update document lifecycle status."""
        now = datetime.now(timezone.utc).isoformat()
        await self._conn.execute(
            "UPDATE documents SET lifecycle = ?, updated_at = ? WHERE document_id = ?",
            (lifecycle.value, now, document_id),
        )
        await self._conn.commit()

    async def update_document(self, doc: LockerDocument) -> None:
        """Full update of a document record."""
        await self._conn.execute(
            """UPDATE documents SET
                owner = ?, department = ?, document_type = ?, case_type = ?,
                serial_number = ?, qr_code = ?, verification_status = ?,
                confidence_score = ?, file_hash = ?, encryption_ref = ?,
                original_filename = ?, file_size = ?, mime_type = ?,
                page_count = ?, ocr_text = ?, extracted_metadata = ?,
                is_duplicate = ?, duplicate_of = ?, preview_ref = ?,
                thumbnail_ref = ?, lifecycle = ?, version = ?,
                perceptual_hash = ?, updated_at = ?
            WHERE document_id = ?""",
            (
                doc.owner, doc.department, doc.document_type.value, doc.case_type,
                doc.serial_number, doc.qr_code, doc.verification_status.value,
                doc.confidence_score, doc.file_hash, doc.encryption_ref,
                doc.original_filename, doc.file_size, doc.mime_type,
                doc.page_count, doc.ocr_text, json.dumps(doc.extracted_metadata),
                int(doc.is_duplicate), doc.duplicate_of, doc.preview_ref,
                doc.thumbnail_ref, doc.lifecycle.value, doc.version,
                doc.extracted_metadata.get("perceptual_hash"),
                doc.updated_at.isoformat(), doc.document_id,
            ),
        )
        await self._conn.commit()

    # ── Duplicate detection helpers ──────────────────────────────────────

    async def find_by_hash(self, file_hash: str) -> Optional[str]:
        """Find an active document with matching content hash."""
        cursor = await self._conn.execute(
            "SELECT document_id FROM documents "
            "WHERE file_hash = ? AND lifecycle NOT IN ('deleted') LIMIT 1",
            (file_hash,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def find_similar_phash(
        self, phash: str, threshold: int = 8
    ) -> Optional[str]:
        """
        Find an active document with similar perceptual hash.
        Uses Hamming distance on hex-encoded pHash strings.
        Simple SQL approach: fetch all and compare in Python.
        """
        cursor = await self._conn.execute(
            "SELECT document_id, perceptual_hash FROM documents "
            "WHERE perceptual_hash IS NOT NULL AND lifecycle NOT IN ('deleted')"
        )
        rows = await cursor.fetchall()

        try:
            import imagehash
            target = imagehash.hex_to_hash(phash)
            for row in rows:
                existing = imagehash.hex_to_hash(row["perceptual_hash"])
                if target - existing <= threshold:
                    return row["document_id"]
        except ImportError:
            pass

        return None

    # ── Version history ──────────────────────────────────────────────────

    async def insert_version(self, ver: DocumentVersion) -> None:
        """Insert an immutable version record."""
        await self._conn.execute(
            """INSERT INTO document_versions (
                version_id, document_id, version, file_hash,
                encryption_ref, file_size, change_summary,
                created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ver.version_id, ver.document_id, ver.version,
                ver.file_hash, ver.encryption_ref, ver.file_size,
                ver.change_summary, ver.created_by, ver.created_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_versions(self, document_id: str) -> List[DocumentVersion]:
        """Get version history for a document, ordered newest first."""
        cursor = await self._conn.execute(
            "SELECT * FROM document_versions WHERE document_id = ? "
            "ORDER BY version DESC",
            (document_id,),
        )
        rows = await cursor.fetchall()
        return [
            DocumentVersion(
                version_id=r["version_id"],
                document_id=r["document_id"],
                version=r["version"],
                file_hash=r["file_hash"],
                encryption_ref=r["encryption_ref"],
                file_size=r["file_size"],
                change_summary=r["change_summary"],
                created_by=r["created_by"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    # ── Deletion requests ────────────────────────────────────────────────

    async def insert_deletion_request(self, req: DeletionRequest) -> None:
        await self._conn.execute(
            """INSERT INTO deletion_requests (
                request_id, document_id, requested_by, reason,
                status, approved_by, reviewed_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                req.request_id, req.document_id, req.requested_by,
                req.reason, req.status.value, req.approved_by,
                req.reviewed_at.isoformat() if req.reviewed_at else None,
                req.created_at.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_deletion_request(self, request_id: str) -> Optional[DeletionRequest]:
        cursor = await self._conn.execute(
            "SELECT * FROM deletion_requests WHERE request_id = ?", (request_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_deletion(row) if row else None

    async def list_deletion_requests(
        self, status: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> List[DeletionRequest]:
        clauses = []
        params: list = []
        if status:
            clauses.append("status = ?")
            params.append(status)

        where = " AND ".join(clauses) if clauses else "1=1"
        params.extend([limit, offset])

        cursor = await self._conn.execute(
            f"SELECT * FROM deletion_requests WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params,
        )
        rows = await cursor.fetchall()
        return [self._row_to_deletion(r) for r in rows]

    async def update_deletion_request(self, req: DeletionRequest) -> None:
        await self._conn.execute(
            """UPDATE deletion_requests SET
                status = ?, approved_by = ?, reviewed_at = ?
            WHERE request_id = ?""",
            (
                req.status.value, req.approved_by,
                req.reviewed_at.isoformat() if req.reviewed_at else None,
                req.request_id,
            ),
        )
        await self._conn.commit()

    # ── Audit log ────────────────────────────────────────────────────────

    async def log_audit(self, record: AuditRecord) -> None:
        """Insert an immutable audit record."""
        await self._conn.execute(
            """INSERT INTO audit_log (
                audit_id, document_id, user_id, action,
                detail, ip_address, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                record.audit_id, record.document_id, record.user_id,
                record.action.value, record.detail,
                record.ip_address, record.timestamp.isoformat(),
            ),
        )
        await self._conn.commit()

    async def get_audit_log(
        self, document_id: str, limit: int = 100
    ) -> List[AuditRecord]:
        cursor = await self._conn.execute(
            "SELECT * FROM audit_log WHERE document_id = ? "
            "ORDER BY timestamp DESC LIMIT ?",
            (document_id, limit),
        )
        rows = await cursor.fetchall()
        return [
            AuditRecord(
                audit_id=r["audit_id"],
                document_id=r["document_id"],
                user_id=r["user_id"],
                action=AuditAction(r["action"]),
                detail=r["detail"],
                ip_address=r["ip_address"],
                timestamp=datetime.fromisoformat(r["timestamp"]),
            )
            for r in rows
        ]

    # ── Row mappers ──────────────────────────────────────────────────────

    @staticmethod
    def _row_to_doc(row: aiosqlite.Row) -> LockerDocument:
        """Map a database row to a LockerDocument."""
        return LockerDocument(
            document_id=row["document_id"],
            owner=row["owner"],
            department=row["department"],
            document_type=DocumentCategory(row["document_type"]),
            case_type=row["case_type"],
            serial_number=row["serial_number"],
            qr_code=row["qr_code"],
            verification_status=VerificationStatus(row["verification_status"]),
            confidence_score=row["confidence_score"],
            file_hash=row["file_hash"],
            encryption_ref=row["encryption_ref"],
            original_filename=row["original_filename"],
            file_size=row["file_size"],
            mime_type=row["mime_type"],
            page_count=row["page_count"],
            ocr_text=row["ocr_text"],
            extracted_metadata=json.loads(row["extracted_metadata"]),
            is_duplicate=bool(row["is_duplicate"]),
            duplicate_of=row["duplicate_of"],
            preview_ref=row["preview_ref"],
            thumbnail_ref=row["thumbnail_ref"],
            lifecycle=DocumentLifecycle(row["lifecycle"]),
            version=row["version"],
            upload_timestamp=datetime.fromisoformat(row["upload_timestamp"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _row_to_deletion(row: aiosqlite.Row) -> DeletionRequest:
        return DeletionRequest(
            request_id=row["request_id"],
            document_id=row["document_id"],
            requested_by=row["requested_by"],
            reason=row["reason"],
            status=DeletionStatus(row["status"]),
            approved_by=row["approved_by"],
            reviewed_at=(
                datetime.fromisoformat(row["reviewed_at"])
                if row["reviewed_at"]
                else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
