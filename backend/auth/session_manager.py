"""
auth/session_manager.py — Device fingerprinting, session lifecycle,
                           IP tracking, and login history.

Device fingerprint
------------------
  SHA-256 of (User-Agent + /24 subnet of client IP + Accept-Language header)
  Stable across browser restarts on the same machine/network.
  Stored in auth.database._devices; looked up on every login.

Account lockout
---------------
  After LOCKOUT_THRESHOLD consecutive failed attempts the account is locked
  for LOCKOUT_DURATION_MINUTES.  A successful login resets the counter.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import Request

try:
    import user_agents as _ua_lib
    _UA_AVAILABLE = True
except ImportError:
    _UA_AVAILABLE = False

from auth import database as db
from auth.models import (
    AccountStatus, AuthMethod, Device, LoginEvent, LoginEventType, Role, Session, User,
)
from core.logging import get_logger

logger = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
LOCKOUT_THRESHOLD      = int(os.getenv("LOCKOUT_THRESHOLD",       "5"))
LOCKOUT_DURATION_MIN   = int(os.getenv("LOCKOUT_DURATION_MINUTES","15"))
SESSION_TTL_HOURS      = int(os.getenv("SESSION_TTL_HOURS",       "8"))


# ── IP helpers ────────────────────────────────────────────────────────────────

def get_client_ip(request: Request) -> str:
    """Extract real client IP, respecting X-Forwarded-For."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def ip_subnet(ip: str) -> str:
    """Return the /24 subnet string for fingerprinting (less churn on DHCP)."""
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3])
    return ip   # IPv6 — use as-is


# ── Device fingerprinting ─────────────────────────────────────────────────────

def compute_fingerprint(request: Request) -> str:
    """Stable device fingerprint from request headers."""
    ua      = request.headers.get("User-Agent", "")
    lang    = request.headers.get("Accept-Language", "")
    ip      = ip_subnet(get_client_ip(request))
    raw     = f"{ua}|{ip}|{lang}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_ua(ua_string: str) -> Tuple[str, str, str, bool]:
    """Return (device_name, browser, os, is_mobile)."""
    if not _UA_AVAILABLE or not ua_string:
        return ua_string[:80] if ua_string else "Unknown", "Unknown", "Unknown", False
    ua  = _ua_lib.parse(ua_string)
    browser   = f"{ua.browser.family} {ua.browser.version_string}".strip()
    os_name   = f"{ua.os.family} {ua.os.version_string}".strip()
    is_mobile = ua.is_mobile or ua.is_tablet
    name      = f"{ua.browser.family} on {ua.os.family}"
    return name, browser, os_name, is_mobile


def get_or_create_device(user_id: str, request: Request) -> Device:
    """
    Look up the device by fingerprint; create a new record if unseen.
    Always updates last_seen and login_count.
    """
    fingerprint = compute_fingerprint(request)
    ua_string   = request.headers.get("User-Agent", "")
    ip          = get_client_ip(request)

    existing = db.get_device_by_fingerprint(fingerprint)
    if existing and existing.user_id == user_id:
        existing.last_seen   = datetime.now(timezone.utc)
        existing.login_count += 1
        existing.ip_address  = ip
        db.save_device(existing)
        return existing

    name, browser, os_name, is_mobile = _parse_ua(ua_string)
    device = Device(
        user_id=user_id,
        fingerprint=fingerprint,
        device_name=name,
        browser=browser,
        os=os_name,
        is_mobile=is_mobile,
        ip_address=ip,
        login_count=1,
    )
    db.save_device(device)
    logger.info("New device registered: user=%s device_id=%s", user_id, device.device_id)
    return device


# ── Session lifecycle ─────────────────────────────────────────────────────────

def create_session(
    user_id:         str,
    role:            Role,
    auth_method:     AuthMethod,
    device_id:       str,
    ip_address:      str,
    user_agent:      str,
    access_token_jti: str,
    refresh_token_hash: str,
    refresh_expires_at: datetime,
) -> Session:
    expires = min(
        refresh_expires_at,
        datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS),
    )
    session = Session(
        user_id=user_id,
        role=role,
        auth_method=auth_method,
        device_id=device_id,
        ip_address=ip_address,
        user_agent=user_agent,
        access_token_jti=access_token_jti,
        refresh_token_hash=refresh_token_hash,
        expires_at=expires,
    )
    db.save_session(session)
    logger.info(
        "Session created: sid=%s user=%s role=%s ip=%s",
        session.session_id, user_id, role.value, ip_address,
    )
    return session


def revoke_session(session_id: str, reason: str = "user_logout") -> bool:
    """Mark session as revoked and add its JTI to the revocation list."""
    session = db.get_session(session_id)
    if not session:
        return False
    session.revoked      = True
    session.revoked_at   = datetime.now(timezone.utc)
    session.revoke_reason = reason
    db.save_session(session)
    db.revoke_jti(session.access_token_jti)
    logger.info("Session revoked: sid=%s reason=%s", session_id, reason)
    return True


def revoke_all_sessions(user_id: str, reason: str = "admin_revoke") -> int:
    """Revoke every active session for a user. Returns count revoked."""
    sessions = db.get_sessions_for_user(user_id)
    for s in sessions:
        revoke_session(s.session_id, reason)
    return len(sessions)


# ── Account lockout ───────────────────────────────────────────────────────────

def record_failed_attempt(user: User) -> bool:
    """
    Increment failed_attempts and lock the account if threshold is reached.
    Returns True if the account is now locked.
    """
    user.failed_attempts += 1
    if user.failed_attempts >= LOCKOUT_THRESHOLD:
        user.status       = AccountStatus.LOCKED
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MIN)
        db.save_user(user)
        logger.warning(
            "Account LOCKED: user=%s after %d failed attempts, until=%s",
            user.user_id, user.failed_attempts, user.locked_until.isoformat(),
        )
        return True
    db.save_user(user)
    return False


def clear_failed_attempts(user: User) -> None:
    """Reset lockout counter after a successful login."""
    user.failed_attempts = 0
    user.status          = AccountStatus.ACTIVE
    user.locked_until    = None
    user.last_login      = datetime.now(timezone.utc)
    db.save_user(user)


def check_account_locked(user: User) -> Optional[str]:
    """
    Return a human-readable message if the account is locked, else None.
    Also auto-unlocks if the lockout period has passed.
    """
    if user.status == AccountStatus.DISABLED:
        return "Account has been disabled. Contact support."
    if user.status == AccountStatus.LOCKED:
        if user.locked_until and datetime.now(timezone.utc) >= user.locked_until:
            # Auto-unlock after the duration
            user.status       = AccountStatus.ACTIVE
            user.failed_attempts = 0
            user.locked_until = None
            db.save_user(user)
            return None
        remaining = ""
        if user.locked_until:
            delta = user.locked_until - datetime.now(timezone.utc)
            mins  = max(1, int(delta.total_seconds() / 60))
            remaining = f" Try again in {mins} minute(s)."
        return f"Account is temporarily locked due to too many failed attempts.{remaining}"
    return None


# ── Login history ─────────────────────────────────────────────────────────────

def log_event(
    user_id:    str,
    event_type: LoginEventType,
    request:    Request,
    session_id: Optional[str] = None,
    device_id:  Optional[str] = None,
    detail:     Optional[str] = None,
) -> None:
    event = LoginEvent(
        user_id=user_id,
        event_type=event_type,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("User-Agent", ""),
        session_id=session_id,
        device_id=device_id,
        detail=detail,
    )
    db.add_login_event(event)
