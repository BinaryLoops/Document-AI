"""
auth/routes.py — All /auth/* endpoints.

Endpoints
---------
  POST /auth/login          — Step 1 for all roles
  POST /auth/otp            — Step 2 for Citizen (phone OTP)
  POST /auth/mfa            — Step 2 for Official/Admin/IssAuth (TOTP/backup)
  POST /auth/logout         — Revoke current session
  POST /auth/refresh        — Rotate access + refresh tokens
  GET  /auth/me             — Current user profile
  GET  /auth/devices        — All registered devices for current user
  POST /auth/revoke-session — Revoke a specific session (or all)
  GET  /auth/history        — Login event history (last 50)
  POST /auth/mfa/setup      — Generate TOTP secret + QR URI + backup codes
  POST /auth/mfa/verify     — Confirm TOTP code to enable MFA

Login flows
-----------
  Citizen:
    POST /auth/login  { role:"citizen", aadhaar_number, phone }
      → { otp_id, masked_phone, next:"otp" }
    POST /auth/otp    { otp_id, code }
      → { access_token, refresh_token, … }

  Government Official / System Admin / Issuing Authority:
    POST /auth/login  { role:"government_official"|"system_admin"|"issuing_authority",
                        employee_id, password }
      → if MFA enabled:  { session_token, next:"mfa" }
      → if MFA disabled: { access_token, refresh_token, … }  (dev only)
    POST /auth/mfa    { session_token, totp_code }   OR   { session_token, backup_code }
      → { access_token, refresh_token, … }
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

import jwt as _jwt

from auth import database as db
from auth.hashing import (
    hash_token, verify_aadhaar, verify_password, verify_token_hash,
)
from auth.jwt_handler import (
    create_token_pair, decode_token_unverified, verify_access_token,
)
from auth.mfa import (
    hash_backup_codes,
    mfa_required_for_role,
    setup_mfa,
    verify_backup_code,
    verify_totp,
)
from auth.models import AccountStatus, AuthMethod, LoginEventType, Role
from auth.otp_handler import OTPError, issue_otp, verify_otp_code
from auth.rbac import Permission, require_auth, require_permission, require_role
from auth.session_manager import (
    check_account_locked,
    clear_failed_attempts,
    create_session,
    get_client_ip,
    get_or_create_device,
    log_event,
    record_failed_attempt,
    revoke_all_sessions,
    revoke_session,
)
from core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

_bearer = HTTPBearer(auto_error=False)

# ── Pending MFA tokens (short-lived, in-memory) ───────────────────────────────
# After password check passes but before TOTP, we issue a short-lived
# "mfa_pending" token so the second factor can reference the user.
# Stored as { token: (user_id, expires_at) }
_MFA_PENDING: Dict[str, tuple] = {}
_MFA_PENDING_TTL_SECONDS = 300   # 5 minutes


def _issue_mfa_pending_token(user_id: str) -> str:
    token     = secrets.token_urlsafe(32)
    expires   = datetime.now(timezone.utc) + timedelta(seconds=_MFA_PENDING_TTL_SECONDS)
    _MFA_PENDING[token] = (user_id, expires)
    return token


def _consume_mfa_pending_token(token: str) -> Optional[str]:
    """Return user_id and remove the token, or None if invalid/expired."""
    entry = _MFA_PENDING.pop(token, None)
    if entry is None:
        return None
    user_id, expires = entry
    if datetime.now(timezone.utc) > expires:
        return None
    return user_id


# ── Request / Response models ─────────────────────────────────────────────────

class LoginRequest(BaseModel):
    role: str = Field(..., description="citizen | government_official | system_admin | issuing_authority")
    # Citizen
    aadhaar_number: Optional[str] = Field(None, description="12-digit Aadhaar number")
    phone:          Optional[str] = Field(None, description="Phone in E.164 format")
    # Official / Admin / IssAuth
    employee_id:    Optional[str] = None
    department_code: Optional[str] = None
    password:       Optional[str] = None


class OTPVerifyRequest(BaseModel):
    otp_id: str
    code:   str = Field(..., min_length=4, max_length=10)


class MFAVerifyRequest(BaseModel):
    session_token: str              # the pending MFA token from /auth/login
    totp_code:     Optional[str] = Field(None, description="6-digit TOTP from authenticator app")
    backup_code:   Optional[str] = Field(None, description="8-char backup code")


class RefreshRequest(BaseModel):
    refresh_token: str


class RevokeSessionRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Specific session ID; omit to revoke all")
    reason:     str = "user_request"


class MFASetupConfirm(BaseModel):
    totp_code: str = Field(..., description="6-digit code from authenticator to confirm setup")


# ── Helper: build final token response ───────────────────────────────────────

async def _finalize_login(user, request: Request, auth_method: AuthMethod) -> Dict[str, Any]:
    """
    Shared final step: create session, issue tokens, log event.
    Called after ALL authentication factors are verified.
    """
    device  = get_or_create_device(user.user_id, request)
    ip      = get_client_ip(request)
    ua      = request.headers.get("User-Agent", "")

    tokens  = create_token_pair(user.user_id, user.role, session_id="pending")

    session = create_session(
        user_id=user.user_id,
        role=user.role,
        auth_method=auth_method,
        device_id=device.device_id,
        ip_address=ip,
        user_agent=ua,
        access_token_jti=tokens["access_jti"],
        refresh_token_hash=tokens["refresh_token_hash"],
        refresh_expires_at=datetime.fromisoformat(tokens["refresh_expires_at"]),
    )

    # Re-mint with real session_id in the JWT payload
    tokens = create_token_pair(
        user.user_id, user.role, session.session_id,
        extra={"jurisdiction": user.jurisdiction} if user.jurisdiction else None,
    )
    # Update session with correct JTI
    session.access_token_jti   = tokens["access_jti"]
    session.refresh_token_hash = tokens["refresh_token_hash"]
    db.save_session(session)

    clear_failed_attempts(user)
    log_event(user.user_id, LoginEventType.SUCCESS, request,
              session_id=session.session_id, device_id=device.device_id)

    try:
        from security.audit import log_audit, AuditCategory, AuditSeverity
        await log_audit(
            action="login_success",
            category=AuditCategory.AUTH,
            severity=AuditSeverity.INFO,
            actor_id=user.user_id,
            actor_name=user.full_name,
            actor_ip=ip,
            resource_type="session",
            resource_id=session.session_id,
            description=f"{user.role} login succeeded via {auth_method}",
        )
    except Exception as e:
        logger.warning("Audit log write failed (non-fatal): %s", e)

    return {
        "access_token":      tokens["access_token"],
        "refresh_token":     tokens["refresh_token"],
        "token_type":        "bearer",
        "expires_at":        tokens["access_expires_at"],
        "session_id":        session.session_id,
        "user":              user.to_public_dict(),
        "permissions":       [p.value for p in
                               __import__("auth.rbac", fromlist=["ROLE_PERMISSIONS"])
                               .ROLE_PERMISSIONS.get(user.role, set())],
    }


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post("/login", summary="Step 1 — authenticate with primary credentials")
async def login(body: LoginRequest, request: Request) -> Dict[str, Any]:
    """
    Primary credential check for all four roles.

    | Role               | Required fields           | Returns                    |
    |--------------------|---------------------------|----------------------------|
    | citizen            | aadhaar_number + phone    | { otp_id, next:"otp" }     |
    | government_official| employee_id + password    | { session_token, next:"mfa" } or tokens |
    | system_admin       | employee_id + password    | { session_token, next:"mfa" } |
    | issuing_authority  | department_code + password| { session_token, next:"mfa" } or tokens |
    """
    ip = get_client_ip(request)

    # -- Validate role ---
    try:
        role = Role(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown role: {body.role}")

    # ── CITIZEN ──────────────────────────────────────────────────────────────
    if role == Role.CITIZEN:
        if not body.aadhaar_number or not body.phone:
            raise HTTPException(400, "aadhaar_number and phone are required for citizens.")

        from auth.hashing import hash_aadhaar
        aadhaar_hash = hash_aadhaar(body.aadhaar_number)
        user = db.get_user_by_aadhaar_hash(aadhaar_hash)

        if user is None:
            # Don't reveal if Aadhaar exists — return same error
            raise HTTPException(401, "Invalid Aadhaar number or phone.")

        lock_msg = check_account_locked(user)
        if lock_msg:
            raise HTTPException(403, lock_msg)

        # Verify phone matches (prevents enumeration via Aadhaar alone)
        if user.phone_number != body.phone:
            locked = record_failed_attempt(user)
            log_event(user.user_id, LoginEventType.FAILED_CREDS, request,
                      detail=f"phone mismatch attempt {user.failed_attempts}")
            if locked:
                raise HTTPException(403, "Account locked due to too many failed attempts.")
            raise HTTPException(401, "Invalid Aadhaar number or phone.")

        otp_id, masked, dev_code = issue_otp(user.user_id, body.phone, purpose="login")
        response = {
            "next":        "otp",
            "otp_id":      otp_id,
            "masked_phone": masked,
            "message":     f"OTP sent to {masked}. Valid for 5 minutes.",
        }
        if dev_code is not None:
            response["dev_otp"] = dev_code
        return response

    # ── OFFICIAL / ADMIN / ISSUING AUTHORITY ─────────────────────────────────
    if role == Role.GOVERNMENT_OFFICIAL:
        if not body.employee_id or not body.password:
            raise HTTPException(400, "employee_id and password are required.")
        user = db.get_user_by_employee_id(body.employee_id)

    elif role == Role.SYSTEM_ADMIN:
        if not body.employee_id or not body.password:
            raise HTTPException(400, "employee_id and password are required.")
        user = db.get_user_by_employee_id(body.employee_id)

    elif role == Role.ISSUING_AUTHORITY:
        if not (body.department_code or body.employee_id) or not body.password:
            raise HTTPException(400, "department_code (or employee_id) and password are required.")
        user = (
            db.get_user_by_dept_code(body.department_code)
            if body.department_code
            else db.get_user_by_employee_id(body.employee_id)
        )
    else:
        raise HTTPException(400, f"Unsupported role: {role}")

    if user is None or user.role != role:
        raise HTTPException(401, "Invalid credentials.")

    lock_msg = check_account_locked(user)
    if lock_msg:
        raise HTTPException(403, lock_msg)

    if not user.password_hash or not verify_password(body.password, user.password_hash):
        locked = record_failed_attempt(user)
        log_event(user.user_id, LoginEventType.FAILED_CREDS, request,
                  detail=f"bad password attempt {user.failed_attempts}")
        try:
            from security.audit import log_audit, AuditCategory, AuditSeverity
            await log_audit(
                action="login_failed",
                category=AuditCategory.AUTH,
                severity=AuditSeverity.WARNING,
                actor_id=user.user_id,
                actor_ip=get_client_ip(request),
                description=f"Failed login attempt ({user.failed_attempts}) for {role}",
            )
        except Exception as e:
            logger.warning("Audit log write failed (non-fatal): %s", e)
        if locked:
            raise HTTPException(403, "Account locked due to too many failed attempts.")
        raise HTTPException(401, "Invalid credentials.")

    # Password correct — check if MFA required
    if mfa_required_for_role(role) and user.mfa_enabled:
        pending_token = _issue_mfa_pending_token(user.user_id)
        return {
            "next":          "mfa",
            "session_token": pending_token,
            "message":       "Enter the 6-digit code from your authenticator app.",
        }

    # MFA not yet set up (dev / first login) — issue tokens directly
    # In production you would force MFA setup here
    logger.warning(
        "User %s (%s) logged in without MFA — MFA not enabled",
        user.user_id, role.value,
    )
    auth_method = {
        Role.GOVERNMENT_OFFICIAL: AuthMethod.EMPLOYEE_MFA,
        Role.SYSTEM_ADMIN:        AuthMethod.ADMIN_MFA,
        Role.ISSUING_AUTHORITY:   AuthMethod.DEPT_CERT,
    }[role]
    return await _finalize_login(user, request, auth_method)


# ── POST /auth/otp ────────────────────────────────────────────────────────────

@router.post("/otp", summary="Step 2 (Citizen) — verify phone OTP")
async def verify_otp_endpoint(body: OTPVerifyRequest, request: Request) -> Dict[str, Any]:
    """Validate the OTP sent to the Citizen's phone and complete login."""
    try:
        record = verify_otp_code(body.otp_id, body.code)
    except OTPError as e:
        user_id = db.get_otp(body.otp_id)
        if user_id:
            log_event(
                user_id.user_id if hasattr(user_id, "user_id") else "",
                LoginEventType.FAILED_OTP,
                request,
                detail=e.message,
            )
        raise HTTPException(status_code=401, detail=e.message)

    user = db.get_user(record.user_id)
    if user is None:
        raise HTTPException(500, "User not found after OTP verification.")

    return await _finalize_login(user, request, AuthMethod.AADHAAR_OTP)


# ── POST /auth/mfa ────────────────────────────────────────────────────────────

@router.post("/mfa", summary="Step 2 (Official/Admin/IssAuth) — verify TOTP or backup code")
async def verify_mfa_endpoint(body: MFAVerifyRequest, request: Request) -> Dict[str, Any]:
    """Complete MFA step using TOTP or a backup code."""
    user_id = _consume_mfa_pending_token(body.session_token)
    if user_id is None:
        raise HTTPException(401, "MFA session expired or invalid. Please log in again.")

    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(401, "User not found.")

    lock_msg = check_account_locked(user)
    if lock_msg:
        raise HTTPException(403, lock_msg)

    verified = False

    if body.totp_code:
        verified = verify_totp(user, body.totp_code)
        if not verified:
            locked = record_failed_attempt(user)
            log_event(user.user_id, LoginEventType.FAILED_MFA, request,
                      detail=f"bad TOTP attempt {user.failed_attempts}")
            if locked:
                raise HTTPException(403, "Account locked due to too many failed attempts.")
            raise HTTPException(401, "Invalid authenticator code.")

    elif body.backup_code:
        matched, updated_hashes = verify_backup_code(user, body.backup_code)
        if not matched:
            locked = record_failed_attempt(user)
            log_event(user.user_id, LoginEventType.FAILED_MFA, request,
                      detail="bad backup code")
            if locked:
                raise HTTPException(403, "Account locked.")
            raise HTTPException(401, "Invalid backup code.")
        # Consume the used backup code
        user.mfa_backup_codes = updated_hashes
        db.save_user(user)
        verified = True

    else:
        raise HTTPException(400, "Provide either totp_code or backup_code.")

    auth_method = {
        Role.GOVERNMENT_OFFICIAL: AuthMethod.EMPLOYEE_MFA,
        Role.SYSTEM_ADMIN:        AuthMethod.ADMIN_MFA,
        Role.ISSUING_AUTHORITY:   AuthMethod.DEPT_CERT,
    }.get(user.role, AuthMethod.EMPLOYEE_MFA)

    return await _finalize_login(user, request, auth_method)


# ── POST /auth/logout ─────────────────────────────────────────────────────────

@router.post("/logout", summary="Revoke current session and invalidate tokens")
async def logout(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Dict[str, Any]:
    """
    Revoke the current access token and its associated session.
    Works even if the token is near-expiry.
    """
    if credentials is None:
        raise HTTPException(401, "No token provided.")

    token = credentials.credentials
    try:
        # Decode without verification to get jti and sid (works on expired tokens too)
        payload = decode_token_unverified(token)
    except Exception:
        raise HTTPException(400, "Malformed token.")

    jti        = payload.get("jti", "")
    session_id = payload.get("sid", "")
    user_id    = payload.get("sub", "")

    # Add JTI to revocation list
    if jti:
        db.revoke_jti(jti)

    # Revoke session record
    if session_id:
        revoke_session(session_id, reason="user_logout")

    if user_id:
        log_event(user_id, LoginEventType.LOGOUT, request, session_id=session_id)

    return {"status": "success", "message": "Logged out successfully."}


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@router.post("/refresh", summary="Rotate access and refresh tokens")
async def refresh_tokens(body: RefreshRequest, request: Request) -> Dict[str, Any]:
    """
    Exchange a valid refresh token for a new access + refresh token pair.
    The old refresh token is invalidated (rotation).
    """
    raw_hash = hash_token(body.refresh_token)

    # Find the session that owns this refresh token
    matching = None
    for session in db._sessions.values():
        if session.refresh_token_hash == raw_hash and session.is_valid():
            matching = session
            break

    if matching is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired refresh token.",
        )

    user = db.get_user(matching.user_id)
    if user is None or user.status != AccountStatus.ACTIVE:
        raise HTTPException(403, "User account unavailable.")

    # Revoke old session (token rotation)
    revoke_session(matching.session_id, reason="token_rotation")

    # Issue new token pair and session
    result = await _finalize_login(user, request, matching.auth_method)
    log_event(user.user_id, LoginEventType.TOKEN_REFRESH, request,
              session_id=result["session_id"])
    return result


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get("/me", summary="Current authenticated user profile")
async def me(user=Depends(require_auth)) -> Dict[str, Any]:
    """Return the profile of the currently authenticated user."""
    from auth.rbac import ROLE_PERMISSIONS
    return {
        **user.to_public_dict(),
        "permissions": [p.value for p in ROLE_PERMISSIONS.get(user.role, set())],
    }


# ── GET /auth/devices ─────────────────────────────────────────────────────────

@router.get("/devices", summary="Devices registered to the current user")
async def list_devices(user=Depends(require_auth)) -> Dict[str, Any]:
    """Return all known devices associated with the authenticated user."""
    devices = db.get_devices_for_user(user.user_id)
    return {
        "user_id": user.user_id,
        "devices": [d.to_dict() for d in devices],
        "count":   len(devices),
    }


# ── POST /auth/revoke-session ─────────────────────────────────────────────────

@router.post("/revoke-session", summary="Revoke a specific session or all sessions")
async def revoke_session_endpoint(
    body: RevokeSessionRequest,
    request: Request,
    user=Depends(require_auth),
) -> Dict[str, Any]:
    """
    Revoke a specific session by ID, or all sessions if session_id is omitted.
    Users can only revoke their own sessions; admins can revoke any.
    """
    if body.session_id:
        session = db.get_session(body.session_id)
        if session is None:
            raise HTTPException(404, "Session not found.")

        # Ownership check — admin can revoke any session
        if session.user_id != user.user_id and user.role != Role.SYSTEM_ADMIN:
            raise HTTPException(403, "Cannot revoke another user's session.")

        revoke_session(body.session_id, reason=body.reason)
        log_event(user.user_id, LoginEventType.SESSION_REVOKED, request,
                  session_id=body.session_id, detail=body.reason)
        return {"status": "success", "revoked_sessions": 1}

    # Revoke all own sessions
    count = revoke_all_sessions(user.user_id, reason=body.reason)
    log_event(user.user_id, LoginEventType.SESSION_REVOKED, request,
              detail=f"all sessions revoked ({count})")
    return {"status": "success", "revoked_sessions": count}


# ── GET /auth/history ─────────────────────────────────────────────────────────

@router.get("/history", summary="Login event history for the current user")
async def login_history(
    limit: int = 50,
    user=Depends(require_auth),
) -> Dict[str, Any]:
    """Return the last N login events (default 50) for the current user."""
    events = db.get_login_events(user.user_id, limit=min(limit, 200))
    return {
        "user_id": user.user_id,
        "events":  [e.to_dict() for e in events],
        "count":   len(events),
    }


# ── POST /auth/mfa/setup ──────────────────────────────────────────────────────

@router.post(
    "/mfa/setup",
    summary="Generate TOTP secret + QR provisioning URI + backup codes",
    dependencies=[Depends(require_role(
        Role.GOVERNMENT_OFFICIAL, Role.SYSTEM_ADMIN, Role.ISSUING_AUTHORITY
    ))],
)
async def mfa_setup(user=Depends(require_auth)) -> Dict[str, Any]:
    """
    Begin MFA setup.  Returns a provisioning URI for QR-code scanning
    and 8 backup codes.

    **Show backup codes to the user exactly once — they cannot be retrieved again.**

    Call POST /auth/mfa/verify with a valid TOTP code to activate MFA.
    """
    secret, uri, plain_codes = setup_mfa(user)

    # Store secret temporarily (not yet enabled until /mfa/verify confirms)
    user.mfa_secret       = secret
    user.mfa_backup_codes = hash_backup_codes(plain_codes)
    db.save_user(user)

    return {
        "provisioning_uri": uri,
        "secret":           secret,     # also show for manual entry
        "backup_codes":     plain_codes,  # shown ONCE — user must save these
        "instructions":     (
            "1. Scan the QR code (or enter the secret) in your authenticator app. "
            "2. POST /auth/mfa/verify with the 6-digit code to activate MFA. "
            "3. Store the backup codes securely — they cannot be shown again."
        ),
    }


# ── POST /auth/mfa/verify ─────────────────────────────────────────────────────

@router.post(
    "/mfa/verify",
    summary="Confirm TOTP code to activate MFA",
    dependencies=[Depends(require_role(
        Role.GOVERNMENT_OFFICIAL, Role.SYSTEM_ADMIN, Role.ISSUING_AUTHORITY
    ))],
)
async def mfa_verify(body: MFASetupConfirm, user=Depends(require_auth)) -> Dict[str, Any]:
    """Verify the TOTP code from the authenticator app and enable MFA."""
    if not user.mfa_secret:
        raise HTTPException(400, "MFA not set up. Call POST /auth/mfa/setup first.")
    if user.mfa_enabled:
        raise HTTPException(400, "MFA is already enabled.")

    if not verify_totp(user, body.totp_code):
        raise HTTPException(401, "Invalid TOTP code. MFA not activated.")

    user.mfa_enabled = True
    db.save_user(user)

    logger.info("MFA activated for user=%s role=%s", user.user_id, user.role.value)
    return {
        "status":  "success",
        "message": "MFA successfully activated. Future logins will require your authenticator app.",
    }


# ── Admin: revoke any user's sessions ────────────────────────────────────────

@router.post(
    "/admin/revoke-user",
    summary="[Admin] Revoke all sessions for a target user",
    dependencies=[Depends(require_role(Role.SYSTEM_ADMIN))],
)
async def admin_revoke_user(
    target_user_id: str,
    request: Request,
    user=Depends(require_auth),
) -> Dict[str, Any]:
    """System Admin — force-revoke all sessions for any user."""
    target = db.get_user(target_user_id)
    if target is None:
        raise HTTPException(404, "Target user not found.")

    count = revoke_all_sessions(target_user_id, reason=f"admin_revoke_by_{user.user_id}")
    log_event(user.user_id, LoginEventType.SESSION_REVOKED, request,
              detail=f"admin revoked all sessions for {target_user_id} ({count} sessions)")

    return {
        "status":           "success",
        "target_user_id":   target_user_id,
        "revoked_sessions": count,
    }


# ── Optional import alias ────────────────────────────────────────────────────
# Allows  from auth.routes import router  in main.py
__all__ = ["router"]
