"""
auth/models.py — All auth domain models.

Dataclasses are used (not ORM) so the module has zero heavy dependencies
and works with any backing store (in-memory dict, SQLite, Firestore, etc.).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Enums ────────────────────────────────────────────────────────────────────

class Role(str, Enum):
    """Four government roles — maps directly to RBAC permission sets."""
    CITIZEN            = "citizen"
    GOVERNMENT_OFFICIAL= "government_official"
    SYSTEM_ADMIN       = "system_admin"
    ISSUING_AUTHORITY  = "issuing_authority"


class AccountStatus(str, Enum):
    ACTIVE   = "active"
    LOCKED   = "locked"       # Too many failed attempts
    DISABLED = "disabled"     # Admin-disabled
    PENDING  = "pending"      # OTP not yet verified (citizen first login)


class AuthMethod(str, Enum):
    """Which credential path was used for this login."""
    AADHAAR_OTP   = "aadhaar_otp"        # Citizen
    EMPLOYEE_MFA  = "employee_mfa"       # Government Official
    ADMIN_MFA     = "admin_mfa"          # System Admin
    DEPT_CERT     = "department_cert"    # Issuing Authority


class TokenType(str, Enum):
    ACCESS  = "access"
    REFRESH = "refresh"


class LoginEventType(str, Enum):
    SUCCESS          = "success"
    FAILED_CREDS     = "failed_credentials"
    FAILED_OTP       = "failed_otp"
    FAILED_MFA       = "failed_mfa"
    LOCKED_OUT       = "locked_out"
    LOGOUT           = "logout"
    TOKEN_REFRESH    = "token_refresh"
    SESSION_REVOKED  = "session_revoked"
    PASSWORD_CHANGED = "password_changed"


# ── User ─────────────────────────────────────────────────────────────────────

@dataclass
class User:
    """
    Universal user record covering all four roles.

    Role-specific fields are Optional — only populate what applies:
      Citizen           → aadhaar_number, phone_number
      Government Official→ employee_id, department, jurisdiction
      System Admin      → employee_id, admin_level
      Issuing Authority → department_code, cert_serial
    """
    # Core identity
    user_id:    str  = field(default_factory=lambda: str(uuid.uuid4()))
    role:       Role = Role.CITIZEN
    status:     AccountStatus = AccountStatus.ACTIVE
    full_name:  str  = ""
    email:      Optional[str] = None

    # Credentials (only the relevant subset is non-None)
    password_hash:    Optional[str] = None   # Official / Admin / IssAuth
    aadhaar_hash:     Optional[str] = None   # Citizen — hashed Aadhaar number
    phone_number:     Optional[str] = None   # Citizen — for OTP delivery
    employee_id:      Optional[str] = None   # Official / Admin
    department_code:  Optional[str] = None   # IssAuth / Official
    jurisdiction:     Optional[str] = None   # Official — e.g. "MH-PUNE"
    admin_level:      int            = 0     # Admin: 1 = super, 2 = dept

    # MFA (TOTP) — for Official / Admin / IssAuth
    mfa_secret:       Optional[str] = None   # base32 TOTP secret
    mfa_enabled:      bool           = False
    mfa_backup_codes: List[str]      = field(default_factory=list)

    # Digital certificate (IssAuth only)
    cert_serial:    Optional[str] = None
    cert_thumbprint: Optional[str] = None

    # Security
    failed_attempts:    int  = 0
    locked_until:       Optional[datetime] = None
    last_login:         Optional[datetime] = None
    require_pwd_change: bool = False

    # Timestamps
    created_at:  datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at:  datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def to_public_dict(self) -> Dict[str, Any]:
        """Safe dict — NO secrets, NO hashes."""
        return {
            "user_id":       self.user_id,
            "role":          self.role.value,
            "status":        self.status.value,
            "full_name":     self.full_name,
            "email":         self.email,
            "employee_id":   self.employee_id,
            "department_code": self.department_code,
            "jurisdiction":  self.jurisdiction,
            "mfa_enabled":   self.mfa_enabled,
            "last_login":    self.last_login.isoformat() if self.last_login else None,
            "created_at":    self.created_at.isoformat(),
        }


# ── Session ───────────────────────────────────────────────────────────────────

@dataclass
class Session:
    """
    A single authenticated session.

    One user can have multiple concurrent sessions (different devices).
    The refresh_token_hash lets us do secure token rotation.
    """
    session_id:         str  = field(default_factory=lambda: str(uuid.uuid4()))
    user_id:            str  = ""
    role:               Role = Role.CITIZEN
    auth_method:        AuthMethod = AuthMethod.AADHAAR_OTP

    # Tokens — store hashes, never raw values
    access_token_jti:   str  = ""   # JWT ID of the current access token
    refresh_token_hash: str  = ""   # bcrypt hash of the refresh token

    # Device & network
    device_id:          str  = ""
    ip_address:         str  = ""
    user_agent:         str  = ""

    # Lifecycle
    created_at:   datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_active:  datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at:   Optional[datetime] = None
    revoked:      bool     = False
    revoked_at:   Optional[datetime] = None
    revoke_reason: Optional[str]     = None

    def is_valid(self) -> bool:
        if self.revoked:
            return False
        if self.expires_at and datetime.now(timezone.utc) > self.expires_at:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id":   self.session_id,
            "user_id":      self.user_id,
            "role":         self.role.value,
            "auth_method":  self.auth_method.value,
            "device_id":    self.device_id,
            "ip_address":   self.ip_address,
            "user_agent":   self.user_agent,
            "created_at":   self.created_at.isoformat(),
            "last_active":  self.last_active.isoformat(),
            "expires_at":   self.expires_at.isoformat() if self.expires_at else None,
            "revoked":      self.revoked,
        }


# ── Device ────────────────────────────────────────────────────────────────────

@dataclass
class Device:
    """
    A registered device associated with a user.
    Populated from User-Agent + IP + accept-language fingerprint.
    """
    device_id:     str  = field(default_factory=lambda: str(uuid.uuid4()))
    user_id:       str  = ""
    fingerprint:   str  = ""          # SHA-256 of (UA + IP-subnet + Accept-Language)
    device_name:   str  = ""          # e.g. "Chrome on Windows"
    browser:       str  = ""
    os:            str  = ""
    is_mobile:     bool = False
    ip_address:    str  = ""
    trusted:       bool = False
    first_seen:    datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen:     datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    login_count:   int  = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id":   self.device_id,
            "device_name": self.device_name,
            "browser":     self.browser,
            "os":          self.os,
            "is_mobile":   self.is_mobile,
            "ip_address":  self.ip_address,
            "trusted":     self.trusted,
            "first_seen":  self.first_seen.isoformat(),
            "last_seen":   self.last_seen.isoformat(),
            "login_count": self.login_count,
        }


# ── OTP Record ────────────────────────────────────────────────────────────────

@dataclass
class OTPRecord:
    """
    A pending OTP verification request.
    Phone OTP is 6-digit, expires in OTP_TTL_SECONDS, max OTP_MAX_ATTEMPTS tries.
    """
    otp_id:      str  = field(default_factory=lambda: str(uuid.uuid4()))
    user_id:     str  = ""
    phone:       str  = ""
    otp_hash:    str  = ""        # bcrypt hash of the 6-digit code
    purpose:     str  = "login"   # login | phone_verify | password_reset
    attempts:    int  = 0
    verified:    bool = False
    created_at:  datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at:  Optional[datetime] = None
    verified_at: Optional[datetime] = None


# ── Login History ─────────────────────────────────────────────────────────────

@dataclass
class LoginEvent:
    """Immutable audit record for every authentication attempt."""
    event_id:    str  = field(default_factory=lambda: str(uuid.uuid4()))
    user_id:     str  = ""
    event_type:  LoginEventType = LoginEventType.SUCCESS
    ip_address:  str  = ""
    user_agent:  str  = ""
    device_id:   Optional[str]  = None
    session_id:  Optional[str]  = None
    detail:      Optional[str]  = None      # e.g. "invalid password attempt 2/5"
    timestamp:   datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id":   self.event_id,
            "user_id":    self.user_id,
            "event_type": self.event_type.value,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "device_id":  self.device_id,
            "session_id": self.session_id,
            "detail":     self.detail,
            "timestamp":  self.timestamp.isoformat(),
        }
