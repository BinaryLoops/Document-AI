"""
auth/database.py — In-memory stores with optional JSON persistence.

All stores are module-level singletons.  The server persists them to
auth_store.json on shutdown (via auth/session_manager.py flush call)
and reloads on startup.  In production, replace with a real DB.

Stores
------
  _users          : dict[user_id, User]
  _sessions       : dict[session_id, Session]
  _devices        : dict[device_id, Device]
  _otps           : dict[otp_id, OTPRecord]
  _login_events   : list[LoginEvent]          (ring-buffer, max 10 000)
  _revoked_jtis   : set[str]                  (JWT IDs that are no longer valid)
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from auth.models import (
    AccountStatus, AuthMethod, Device, LoginEvent, OTPRecord, Role, Session, User,
)
from core.logging import get_logger

logger = get_logger(__name__)

# ── Store path ────────────────────────────────────────────────────────────────
_STORE_PATH = Path(os.getenv("AUTH_STORE_PATH", "auth_store.json"))
_MAX_EVENTS = 10_000          # ring-buffer cap for login events
_lock       = threading.RLock()

# ── In-memory stores ─────────────────────────────────────────────────────────
_users:        Dict[str, User]        = {}
_sessions:     Dict[str, Session]     = {}
_devices:      Dict[str, Device]      = {}
_otps:         Dict[str, OTPRecord]   = {}
_login_events: List[LoginEvent]       = []
_revoked_jtis: Set[str]               = set()


# ── Low-level accessors ───────────────────────────────────────────────────────

def get_user(user_id: str) -> Optional[User]:
    return _users.get(user_id)


def get_user_by_employee_id(employee_id: str) -> Optional[User]:
    for u in _users.values():
        if u.employee_id == employee_id:
            return u
    return None


def get_user_by_aadhaar_hash(aadhaar_hash: str) -> Optional[User]:
    for u in _users.values():
        if u.aadhaar_hash == aadhaar_hash:
            return u
    return None


def get_user_by_phone(phone: str) -> Optional[User]:
    for u in _users.values():
        if u.phone_number == phone:
            return u
    return None


def get_user_by_dept_code(dept_code: str) -> Optional[User]:
    for u in _users.values():
        if u.department_code == dept_code:
            return u
    return None


def save_user(user: User) -> None:
    with _lock:
        user.touch()
        _users[user.user_id] = user


def get_session(session_id: str) -> Optional[Session]:
    return _sessions.get(session_id)


def save_session(session: Session) -> None:
    with _lock:
        _sessions[session.session_id] = session


def delete_session(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)


def get_sessions_for_user(user_id: str) -> List[Session]:
    return [s for s in _sessions.values() if s.user_id == user_id and s.is_valid()]


def get_device(device_id: str) -> Optional[Device]:
    return _devices.get(device_id)


def get_device_by_fingerprint(fingerprint: str) -> Optional[Device]:
    for d in _devices.values():
        if d.fingerprint == fingerprint:
            return d
    return None


def get_devices_for_user(user_id: str) -> List[Device]:
    return [d for d in _devices.values() if d.user_id == user_id]


def save_device(device: Device) -> None:
    with _lock:
        _devices[device.device_id] = device


def save_otp(otp: OTPRecord) -> None:
    with _lock:
        _otps[otp.otp_id] = otp


def get_otp(otp_id: str) -> Optional[OTPRecord]:
    return _otps.get(otp_id)


def get_latest_otp(user_id: str, purpose: str = "login") -> Optional[OTPRecord]:
    """Return the most recent un-verified, unexpired OTP for a user."""
    now = datetime.now(timezone.utc)
    candidates = [
        o for o in _otps.values()
        if o.user_id == user_id
        and o.purpose == purpose
        and not o.verified
        and (o.expires_at is None or o.expires_at > now)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda o: o.created_at)


def invalidate_user_otps(user_id: str, purpose: str = "login") -> None:
    """Expire all pending OTPs for a user (after successful verify or new issue)."""
    with _lock:
        for otp in _otps.values():
            if otp.user_id == user_id and otp.purpose == purpose:
                otp.verified = True


def add_login_event(event: LoginEvent) -> None:
    with _lock:
        _login_events.append(event)
        if len(_login_events) > _MAX_EVENTS:
            del _login_events[: len(_login_events) - _MAX_EVENTS]


def get_login_events(user_id: str, limit: int = 50) -> List[LoginEvent]:
    events = [e for e in _login_events if e.user_id == user_id]
    return sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]


def revoke_jti(jti: str) -> None:
    with _lock:
        _revoked_jtis.add(jti)


def is_jti_revoked(jti: str) -> bool:
    return jti in _revoked_jtis


# ── Persistence ───────────────────────────────────────────────────────────────

def _dt(val: Optional[str]) -> Optional[datetime]:
    if val is None:
        return None
    try:
        return datetime.fromisoformat(val)
    except (ValueError, TypeError):
        return None


def load() -> None:
    """Load all stores from auth_store.json if it exists."""
    global _users, _sessions, _devices, _otps, _login_events, _revoked_jtis
    if not _STORE_PATH.exists():
        logger.info("No auth store found at %s — starting fresh with demo users", _STORE_PATH)
        _seed_demo_users()
        return
    try:
        raw = json.loads(_STORE_PATH.read_text(encoding="utf-8"))

        # Users
        for d in raw.get("users", {}).values():
            u = User(**{
                k: v for k, v in d.items()
                if k in User.__dataclass_fields__
            })
            for dt_field in ("locked_until", "last_login", "created_at", "updated_at"):
                setattr(u, dt_field, _dt(getattr(u, dt_field)))
            u.role   = Role(u.role)
            u.status = AccountStatus(u.status)
            _users[u.user_id] = u

        # Sessions
        for d in raw.get("sessions", {}).values():
            s = Session(**{k: v for k, v in d.items() if k in Session.__dataclass_fields__})
            for dt_field in ("created_at", "last_active", "expires_at", "revoked_at"):
                setattr(s, dt_field, _dt(getattr(s, dt_field)))
            s.role        = Role(s.role)
            s.auth_method = AuthMethod(s.auth_method)
            _sessions[s.session_id] = s

        # Devices
        for d in raw.get("devices", {}).values():
            dev = Device(**{k: v for k, v in d.items() if k in Device.__dataclass_fields__})
            dev.first_seen = _dt(dev.first_seen) or datetime.now(timezone.utc)
            dev.last_seen  = _dt(dev.last_seen)  or datetime.now(timezone.utc)
            _devices[dev.device_id] = dev

        # OTPs
        for d in raw.get("otps", {}).values():
            o = OTPRecord(**{k: v for k, v in d.items() if k in OTPRecord.__dataclass_fields__})
            o.created_at  = _dt(o.created_at)  or datetime.now(timezone.utc)
            o.expires_at  = _dt(o.expires_at)
            o.verified_at = _dt(o.verified_at)
            _otps[o.otp_id] = o

        # Events
        for d in raw.get("login_events", []):
            from auth.models import LoginEventType
            e = LoginEvent(**{k: v for k, v in d.items() if k in LoginEvent.__dataclass_fields__})
            e.event_type = LoginEventType(e.event_type)
            e.timestamp  = _dt(e.timestamp) or datetime.now(timezone.utc)
            _login_events.append(e)

        _revoked_jtis = set(raw.get("revoked_jtis", []))

        # Always ensure demo users exist (idempotent — won't duplicate)
        _ensure_demo_users()

        logger.info(
            "Auth store loaded: %d users, %d sessions, %d devices",
            len(_users), len(_sessions), len(_devices),
        )
    except Exception as e:
        logger.error("Failed to load auth store: %s — starting fresh", e, exc_info=True)
        _seed_demo_users()


def flush() -> None:
    """Persist all in-memory stores to auth_store.json."""
    try:
        def _ser(obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            if isinstance(obj, (Role, AccountStatus, AuthMethod)):
                return obj.value
            raise TypeError(f"Not serializable: {type(obj)}")

        def _to_dict(obj) -> dict:
            import dataclasses
            return dataclasses.asdict(obj)

        payload = {
            "users":        {uid: _to_dict(u) for uid, u in _users.items()},
            "sessions":     {sid: _to_dict(s) for sid, s in _sessions.items()},
            "devices":      {did: _to_dict(d) for did, d in _devices.items()},
            "otps":         {oid: _to_dict(o) for oid, o in _otps.items()},
            "login_events": [_to_dict(e) for e in _login_events[-1000:]],  # keep last 1k
            "revoked_jtis": list(_revoked_jtis),
        }
        _STORE_PATH.write_text(
            json.dumps(payload, default=_ser, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Auth store persisted to %s", _STORE_PATH)
    except Exception as e:
        logger.error("Failed to flush auth store: %s", e, exc_info=True)


# ── Demo seed data ────────────────────────────────────────────────────────────

def _ensure_demo_users() -> None:
    """Add any missing demo users (idempotent — safe to call on every load)."""
    DEMO_IDS = {
        "demo-citizen-001", "demo-official-001",
        "demo-admin-001",   "demo-issauth-001",
    }
    if DEMO_IDS.issubset(_users.keys()):
        return   # all demo users already present
    _seed_demo_users()


def _seed_demo_users() -> None:
    """
    Create one demo user per role so the system is testable immediately.
    Passwords/Aadhaar are all dev-only; change before production.
    """
    from auth.hashing import hash_password, hash_aadhaar

    demo: list[User] = [
        # Citizen — logs in with Aadhaar + OTP
        User(
            user_id="demo-citizen-001",
            role=Role.CITIZEN,
            full_name="Ravi Kumar (Demo Citizen)",
            phone_number="+919876543210",
            aadhaar_hash=hash_aadhaar("123456789012"),
            status=AccountStatus.ACTIVE,
        ),
        # Government Official — employee-id + password + MFA
        User(
            user_id="demo-official-001",
            role=Role.GOVERNMENT_OFFICIAL,
            full_name="Priya Sharma (Demo Official)",
            employee_id="GOV-MH-10042",
            department_code="REVENUE-MH",
            jurisdiction="MH-PUNE",
            password_hash=hash_password("Official@1234"),
            status=AccountStatus.ACTIVE,
        ),
        # System Admin
        User(
            user_id="demo-admin-001",
            role=Role.SYSTEM_ADMIN,
            full_name="Admin User (Demo)",
            employee_id="ADMIN-001",
            admin_level=1,
            password_hash=hash_password("Admin@9999"),
            status=AccountStatus.ACTIVE,
        ),
        # Issuing Authority
        User(
            user_id="demo-issauth-001",
            role=Role.ISSUING_AUTHORITY,
            full_name="District Collector Office (Demo)",
            department_code="COLLECTOR-PUNE",
            employee_id="ISS-PUNE-001",
            cert_serial="CERT-2026-PUNE-001",
            cert_thumbprint="ab:cd:ef:12:34",
            password_hash=hash_password("IssAuth@5678"),
            status=AccountStatus.ACTIVE,
        ),
    ]

    for u in demo:
        _users[u.user_id] = u

    logger.info("Seeded %d demo users (development mode)", len(demo))
