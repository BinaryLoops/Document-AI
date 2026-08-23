"""
auth/jwt_handler.py — JWT access-token and refresh-token lifecycle.

Token design
------------
  Access token  : HS256, short-lived (ACCESS_TOKEN_TTL_MINUTES, default 30)
  Refresh token : opaque random string stored as SHA-256 hash in Session;
                  has its own TTL (REFRESH_TOKEN_TTL_DAYS, default 7)

Payload claims
--------------
  sub   : user_id
  role  : Role.value
  jti   : unique JWT ID (used for revocation)
  sid   : session_id
  type  : "access"
  iat / exp : standard

Revocation
----------
  On logout/revoke the jti is added to auth.database._revoked_jtis.
  The verify() function checks this set before returning a payload.
"""

from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from auth.hashing import hash_token
from auth.models import Role, TokenType
from core.logging import get_logger

logger = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
_SECRET_ENV            = "JWT_SECRET_KEY"
_ALGORITHM             = "HS256"
_ACCESS_TTL_MINUTES    = int(os.getenv("ACCESS_TOKEN_TTL_MINUTES",  "30"))
_REFRESH_TTL_DAYS      = int(os.getenv("REFRESH_TOKEN_TTL_DAYS",    "7"))
_ISSUER                = os.getenv("JWT_ISSUER", "documind-ai")


def _secret() -> str:
    key = os.getenv(_SECRET_ENV, "")
    if not key:
        logger.warning(
            "JWT_SECRET_KEY not set — using insecure dev secret. "
            "Generate with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
        key = "dev-jwt-secret-change-in-production-please"
    return key


# ── Access token ──────────────────────────────────────────────────────────────

def create_access_token(
    user_id:    str,
    role:       Role,
    session_id: str,
    extra:      Optional[Dict[str, Any]] = None,
) -> Tuple[str, str, datetime]:
    """
    Mint a signed JWT access token.

    Returns
    -------
    (token_string, jti, expires_at)
    """
    now        = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=_ACCESS_TTL_MINUTES)
    jti        = str(uuid.uuid4())

    payload: Dict[str, Any] = {
        "sub":  user_id,
        "role": role.value,
        "sid":  session_id,
        "jti":  jti,
        "type": TokenType.ACCESS.value,
        "iss":  _ISSUER,
        "iat":  now,
        "exp":  expires_at,
    }
    if extra:
        payload.update(extra)

    token = jwt.encode(payload, _secret(), algorithm=_ALGORITHM)
    return token, jti, expires_at


# ── Refresh token ─────────────────────────────────────────────────────────────

def create_refresh_token() -> Tuple[str, str, datetime]:
    """
    Generate an opaque refresh token.

    Returns
    -------
    (raw_token, token_hash, expires_at)

    The raw_token is sent to the client ONCE.
    The token_hash is stored server-side in the Session record.
    """
    raw        = secrets.token_urlsafe(64)
    token_hash = hash_token(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(days=_REFRESH_TTL_DAYS)
    return raw, token_hash, expires_at


# ── Token pair ────────────────────────────────────────────────────────────────

def create_token_pair(
    user_id:    str,
    role:       Role,
    session_id: str,
    extra:      Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create both an access token and a refresh token in one call.

    Returns a dict ready to be returned directly as an API response.
    """
    access_token, jti, access_exp = create_access_token(user_id, role, session_id, extra)
    refresh_raw, refresh_hash, refresh_exp = create_refresh_token()

    return {
        "access_token":       access_token,
        "refresh_token":      refresh_raw,       # raw — send to client
        "refresh_token_hash": refresh_hash,      # hash — store server-side
        "token_type":         "bearer",
        "access_jti":         jti,
        "access_expires_at":  access_exp.isoformat(),
        "refresh_expires_at": refresh_exp.isoformat(),
    }


# ── Verification ──────────────────────────────────────────────────────────────

def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate an access token.

    Raises
    ------
    jwt.ExpiredSignatureError  — token has expired
    jwt.InvalidTokenError      — token is malformed or revoked
    """
    from auth.database import is_jti_revoked

    try:
        payload = jwt.decode(
            token,
            _secret(),
            algorithms=[_ALGORITHM],
            issuer=_ISSUER,
        )
    except ExpiredSignatureError:
        raise
    except InvalidTokenError as e:
        raise InvalidTokenError(f"Token validation failed: {e}") from e

    # Check revocation list
    jti = payload.get("jti", "")
    if is_jti_revoked(jti):
        raise InvalidTokenError("Token has been revoked")

    # Check type
    if payload.get("type") != TokenType.ACCESS.value:
        raise InvalidTokenError("Wrong token type")

    return payload


def decode_token_unverified(token: str) -> Dict[str, Any]:
    """Decode without signature check — for extracting jti on logout."""
    return jwt.decode(
        token,
        options={"verify_signature": False, "verify_exp": False},
        algorithms=[_ALGORITHM],
    )
