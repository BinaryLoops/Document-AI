"""
tracking/database.py -- Async SQLite persistence for Tracking & Notifications.

Tables:
  - tracking_records: Full application tracking state
  - tracking_events:  Stage transition history (audit trail)
  - notifications:    User notifications with read status
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from tracking.models import (
    Notification,
    NotificationType,
    NOTIFICATION_TEMPLATES,
    TrackingEvent,
    TrackingRecord,
    TrackingStage,
)

logger = logging.getLogger(__name__)

# Module-level DB connection
_db: Optional[aiosqlite.Connection] = None

# ETA estimates per stage (hours from submission)
_STAGE_ETA_HOURS: Dict[str, int] = {
    TrackingStage.SUBMITTED.value:         0,
    TrackingStage.VERIFICATION.value:      24,
    TrackingStage.OFFICER_REVIEW.value:    72,
    TrackingStage.ISSUING_AUTHORITY.value: 120,
    TrackingStage.GENERATED.value:         144,
    TrackingStage.PRINTED.value:           168,
    TrackingStage.DISPATCHED.value:        192,
    TrackingStage.DELIVERED.value:         240,
}


async def init_db(db_path: str = "tracking.db") -> aiosqlite.Connection:
    """Initialize the tracking database and create tables."""
    global _db
    _db = await aiosqlite.connect(db_path)
    _db.row_factory = aiosqlite.Row

    await _db.executescript("""
        CREATE TABLE IF NOT EXISTS tracking_records (
            application_id    TEXT PRIMARY KEY,
            document_id       TEXT DEFAULT '',
            document_type     TEXT DEFAULT '',
            document_name     TEXT DEFAULT '',
            applicant_id      TEXT DEFAULT '',
            applicant_name    TEXT DEFAULT '',
            current_stage     TEXT DEFAULT 'submitted',
            department        TEXT DEFAULT '',
            assigned_officer  TEXT DEFAULT '',
            assigned_officer_name TEXT DEFAULT '',
            eta               TEXT DEFAULT '',
            created_at        TEXT NOT NULL,
            updated_at        TEXT NOT NULL,
            metadata_json     TEXT DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS tracking_events (
            event_id      TEXT PRIMARY KEY,
            application_id TEXT NOT NULL,
            stage         TEXT NOT NULL,
            timestamp     TEXT NOT NULL,
            officer_id    TEXT DEFAULT '',
            officer_name  TEXT DEFAULT '',
            department    TEXT DEFAULT '',
            notes         TEXT DEFAULT '',
            metadata_json TEXT DEFAULT '{}',
            FOREIGN KEY (application_id) REFERENCES tracking_records(application_id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            notification_id   TEXT PRIMARY KEY,
            user_id           TEXT NOT NULL,
            notification_type TEXT NOT NULL,
            title             TEXT DEFAULT '',
            message           TEXT DEFAULT '',
            is_read           INTEGER DEFAULT 0,
            application_id    TEXT DEFAULT '',
            document_id       TEXT DEFAULT '',
            created_at        TEXT NOT NULL,
            metadata_json     TEXT DEFAULT '{}'
        );

        CREATE INDEX IF NOT EXISTS idx_tracking_applicant ON tracking_records(applicant_id);
        CREATE INDEX IF NOT EXISTS idx_tracking_document  ON tracking_records(document_id);
        CREATE INDEX IF NOT EXISTS idx_events_app         ON tracking_events(application_id);
        CREATE INDEX IF NOT EXISTS idx_notif_user         ON notifications(user_id);
        CREATE INDEX IF NOT EXISTS idx_notif_unread       ON notifications(user_id, is_read);
    """)

    await _db.commit()
    logger.info("Tracking database initialized: %s", db_path)
    return _db


async def close_db():
    """Close the database connection."""
    global _db
    if _db:
        await _db.close()
        _db = None


def _get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Tracking database not initialized. Call init_db() first.")
    return _db


# ── Tracking Records ────────────────────────────────────────────────────────

async def create_tracking_record(record: TrackingRecord) -> TrackingRecord:
    """Create a new tracking record."""
    db = _get_db()

    # Calculate initial ETA
    if not record.eta:
        record.eta = _calculate_eta(record.current_stage, record.created_at)

    await db.execute(
        """INSERT INTO tracking_records
           (application_id, document_id, document_type, document_name,
            applicant_id, applicant_name, current_stage, department,
            assigned_officer, assigned_officer_name, eta, created_at,
            updated_at, metadata_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record.application_id, record.document_id, record.document_type,
            record.document_name, record.applicant_id, record.applicant_name,
            record.current_stage, record.department, record.assigned_officer,
            record.assigned_officer_name, record.eta, record.created_at,
            record.updated_at, json.dumps(record.metadata),
        ),
    )

    # Add initial event
    event = TrackingEvent(
        stage=record.current_stage,
        notes="Application submitted",
    )
    await _add_event(record.application_id, event)

    await db.commit()
    logger.info("Created tracking record: %s", record.application_id)
    return record


async def get_tracking_record(application_id: str) -> Optional[TrackingRecord]:
    """Get a tracking record by application ID."""
    db = _get_db()
    cursor = await db.execute(
        "SELECT * FROM tracking_records WHERE application_id = ?",
        (application_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    record = _row_to_record(row)

    # Load history
    events_cursor = await db.execute(
        "SELECT * FROM tracking_events WHERE application_id = ? ORDER BY timestamp ASC",
        (application_id,),
    )
    events = await events_cursor.fetchall()
    record.history = [_row_to_event(e).to_dict() for e in events]

    return record


async def get_tracking_by_document(document_id: str) -> Optional[TrackingRecord]:
    """Get tracking record by document ID."""
    db = _get_db()
    cursor = await db.execute(
        "SELECT * FROM tracking_records WHERE document_id = ?",
        (document_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None
    record = _row_to_record(row)

    events_cursor = await db.execute(
        "SELECT * FROM tracking_events WHERE application_id = ? ORDER BY timestamp ASC",
        (record.application_id,),
    )
    events = await events_cursor.fetchall()
    record.history = [_row_to_event(e).to_dict() for e in events]
    return record


async def update_stage(
    application_id: str,
    new_stage: TrackingStage,
    officer_id: str = "",
    officer_name: str = "",
    department: str = "",
    notes: str = "",
) -> Optional[TrackingRecord]:
    """
    Advance an application to a new stage.
    Creates a tracking event and optionally triggers a notification.
    """
    db = _get_db()
    record = await get_tracking_record(application_id)
    if not record:
        return None

    now = datetime.now(timezone.utc).isoformat()
    new_eta = _calculate_eta(new_stage.value, record.created_at)

    await db.execute(
        """UPDATE tracking_records
           SET current_stage = ?, updated_at = ?, eta = ?,
               assigned_officer = COALESCE(NULLIF(?, ''), assigned_officer),
               assigned_officer_name = COALESCE(NULLIF(?, ''), assigned_officer_name),
               department = COALESCE(NULLIF(?, ''), department)
           WHERE application_id = ?""",
        (new_stage.value, now, new_eta, officer_id, officer_name,
         department, application_id),
    )

    event = TrackingEvent(
        stage=new_stage.value,
        officer_id=officer_id,
        officer_name=officer_name,
        department=department,
        notes=notes,
    )
    await _add_event(application_id, event)
    await db.commit()

    # Create notification for the applicant
    notif_type = _stage_to_notification(new_stage)
    if notif_type and record.applicant_id:
        await create_notification(
            user_id=record.applicant_id,
            notification_type=notif_type,
            doc_name=record.document_name or record.document_type,
            application_id=application_id,
            document_id=record.document_id,
            reason=notes,
            status=new_stage.value.replace("_", " ").title(),
        )

    logger.info("Stage updated: %s -> %s", application_id, new_stage.value)
    return await get_tracking_record(application_id)


async def _add_event(application_id: str, event: TrackingEvent):
    """Insert a tracking event."""
    db = _get_db()
    await db.execute(
        """INSERT INTO tracking_events
           (event_id, application_id, stage, timestamp, officer_id,
            officer_name, department, notes, metadata_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            event.event_id, application_id, event.stage, event.timestamp,
            event.officer_id, event.officer_name, event.department,
            event.notes, json.dumps(event.metadata),
        ),
    )


# ── Notifications ───────────────────────────────────────────────────────────

async def create_notification(
    user_id: str,
    notification_type: NotificationType,
    doc_name: str = "",
    application_id: str = "",
    document_id: str = "",
    reason: str = "",
    status: str = "",
    location: str = "",
    **extra,
) -> Notification:
    """Create and persist a notification for a user."""
    db = _get_db()

    # Build message from template
    template = NOTIFICATION_TEMPLATES.get(notification_type, "You have a new notification.")
    message = template.format(
        doc_name=doc_name, reason=reason, status=status, location=location,
    )

    title = notification_type.value.replace("_", " ").title()

    notif = Notification(
        user_id=user_id,
        notification_type=notification_type.value,
        title=title,
        message=message,
        application_id=application_id,
        document_id=document_id,
        metadata=extra,
    )

    await db.execute(
        """INSERT INTO notifications
           (notification_id, user_id, notification_type, title, message,
            is_read, application_id, document_id, created_at, metadata_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            notif.notification_id, notif.user_id, notif.notification_type,
            notif.title, notif.message, 0, notif.application_id,
            notif.document_id, notif.created_at, json.dumps(notif.metadata),
        ),
    )
    await db.commit()

    logger.info("Notification created: %s for user %s", notif.notification_type, user_id)
    return notif


async def get_notifications(
    user_id: str,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> List[Notification]:
    """Get notifications for a user."""
    db = _get_db()
    query = "SELECT * FROM notifications WHERE user_id = ?"
    params: list = [user_id]

    if unread_only:
        query += " AND is_read = 0"

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [_row_to_notification(r) for r in rows]


async def get_unread_count(user_id: str) -> int:
    """Get the number of unread notifications."""
    db = _get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,),
    )
    row = await cursor.fetchone()
    return row[0] if row else 0


async def mark_notifications_read(
    user_id: str,
    notification_ids: Optional[List[str]] = None,
) -> int:
    """
    Mark notifications as read.
    If notification_ids is None, marks ALL unread notifications as read.
    Returns the number of notifications updated.
    """
    db = _get_db()

    if notification_ids:
        placeholders = ",".join("?" * len(notification_ids))
        cursor = await db.execute(
            f"""UPDATE notifications SET is_read = 1
                WHERE user_id = ? AND notification_id IN ({placeholders})
                AND is_read = 0""",
            [user_id] + notification_ids,
        )
    else:
        cursor = await db.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
            (user_id,),
        )

    await db.commit()
    count = cursor.rowcount
    logger.info("Marked %d notifications as read for user %s", count, user_id)
    return count


# ── Helpers ─────────────────────────────────────────────────────────────────

def _calculate_eta(stage: str, created_at: str) -> str:
    """Calculate ETA based on stage and creation time."""
    try:
        created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        remaining_hours = _STAGE_ETA_HOURS.get(TrackingStage.DELIVERED.value, 240)
        stage_hours = _STAGE_ETA_HOURS.get(stage, 0)
        eta_hours = remaining_hours - stage_hours
        eta_dt = datetime.now(timezone.utc) + timedelta(hours=max(eta_hours, 0))
        return eta_dt.isoformat()
    except (ValueError, TypeError):
        return ""


def _stage_to_notification(stage: TrackingStage) -> Optional[NotificationType]:
    """Map a tracking stage to a notification type."""
    return {
        TrackingStage.SUBMITTED:         NotificationType.UPLOAD_SUCCESSFUL,
        TrackingStage.VERIFICATION:      NotificationType.STATUS_UPDATE,
        TrackingStage.OFFICER_REVIEW:    NotificationType.MANUAL_REVIEW,
        TrackingStage.ISSUING_AUTHORITY: NotificationType.STATUS_UPDATE,
        TrackingStage.GENERATED:         NotificationType.DOCUMENT_GENERATED,
        TrackingStage.PRINTED:           NotificationType.STATUS_UPDATE,
        TrackingStage.DISPATCHED:        NotificationType.DISPATCHED,
        TrackingStage.DELIVERED:         NotificationType.DELIVERED,
        TrackingStage.REJECTED:          NotificationType.DOCUMENT_REJECTED,
    }.get(stage)


def _row_to_record(row) -> TrackingRecord:
    return TrackingRecord(
        application_id=row["application_id"],
        document_id=row["document_id"],
        document_type=row["document_type"],
        document_name=row["document_name"],
        applicant_id=row["applicant_id"],
        applicant_name=row["applicant_name"],
        current_stage=row["current_stage"],
        department=row["department"],
        assigned_officer=row["assigned_officer"],
        assigned_officer_name=row["assigned_officer_name"],
        eta=row["eta"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        metadata=json.loads(row["metadata_json"] or "{}"),
    )


def _row_to_event(row) -> TrackingEvent:
    return TrackingEvent(
        event_id=row["event_id"],
        stage=row["stage"],
        timestamp=row["timestamp"],
        officer_id=row["officer_id"],
        officer_name=row["officer_name"],
        department=row["department"],
        notes=row["notes"],
        metadata=json.loads(row["metadata_json"] or "{}"),
    )


def _row_to_notification(row) -> Notification:
    return Notification(
        notification_id=row["notification_id"],
        user_id=row["user_id"],
        notification_type=row["notification_type"],
        title=row["title"],
        message=row["message"],
        is_read=bool(row["is_read"]),
        application_id=row["application_id"],
        document_id=row["document_id"],
        created_at=row["created_at"],
        metadata=json.loads(row["metadata_json"] or "{}"),
    )
