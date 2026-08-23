"""
auth/rbac.py — Role-Based Access Control.

Permission enum
---------------
Every action in the system is a Permission value.  The ROLE_PERMISSIONS
dict maps each Role to its allowed set.

FastAPI dependencies
--------------------
  require_auth()               → returns current User (any authenticated role)
  require_role(*roles)         → returns current User if role matches
  require_permission(perm)     → returns current User if they have the permission
  optional_auth()              → returns User or None (for public-ish endpoints)

All dependencies extract the Bearer token from the Authorization header,
verify it via jwt_handler.verify_access_token(), and resolve the User from
auth.database.

RBAC rules from spec
--------------------
  Citizen          — read own docs, upload, request generation
  Govt Official    — assigned jurisdiction only, upload case files, verify
                     CANNOT edit issued documents
  System Admin     — audit, monitor, manage departments
                     CANNOT edit issued documents
  Issuing Authority— generate, digitally sign, revoke, reissue
"""

from __future__ import annotations

import os
from enum import Enum, auto
from functools import lru_cache
from typing import Optional, Set

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import jwt as _jwt

from auth import database as db
from auth.jwt_handler import verify_access_token
from auth.models import AccountStatus, Role, User
from core.logging import get_logger

logger = get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)


# ── Permissions ───────────────────────────────────────────────────────────────

class Permission(str, Enum):
    # Document reads
    READ_OWN_DOCUMENTS      = "read_own_documents"
    READ_CASE_DOCUMENTS     = "read_case_documents"
    READ_ALL_DOCUMENTS      = "read_all_documents"

    # Uploads
    UPLOAD_DOCUMENTS        = "upload_documents"
    UPLOAD_CASE_FILES       = "upload_case_files"

    # Generation / issuance
    REQUEST_GENERATION      = "request_generation"
    GENERATE_DOCUMENT       = "generate_document"
    DIGITALLY_SIGN          = "digitally_sign"
    REVOKE_DOCUMENT         = "revoke_document"
    REISSUE_DOCUMENT        = "reissue_document"

    # Verification
    VERIFY_DOCUMENT         = "verify_document"
    VERIFY_JURISDICTION     = "verify_jurisdiction"    # Official: own jurisdiction only

    # Admin
    AUDIT_LOGS              = "audit_logs"
    MONITOR_SYSTEM          = "monitor_system"
    MANAGE_DEPARTMENTS      = "manage_departments"
    MANAGE_USERS            = "manage_users"

    # Explicitly DENIED for certain roles (checked separately in middleware)
    # "edit_issued_document" is NOT in any role's set — enforced by absence


# ── Role → Permission mapping ─────────────────────────────────────────────────

ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {

    Role.CITIZEN: {
        Permission.READ_OWN_DOCUMENTS,
        Permission.UPLOAD_DOCUMENTS,
        Permission.REQUEST_GENERATION,
    },

    Role.GOVERNMENT_OFFICIAL: {
        Permission.READ_CASE_DOCUMENTS,
        Permission.UPLOAD_CASE_FILES,
        Permission.VERIFY_DOCUMENT,
        Permission.VERIFY_JURISDICTION,
        # NOTE: No GENERATE_DOCUMENT / DIGITALLY_SIGN / REVOKE
        # NOTE: No AUDIT_LOGS / MANAGE_DEPARTMENTS
        # NOTE: No edit_issued_document (not in any role)
    },

    Role.SYSTEM_ADMIN: {
        Permission.READ_ALL_DOCUMENTS,
        Permission.AUDIT_LOGS,
        Permission.MONITOR_SYSTEM,
        Permission.MANAGE_DEPARTMENTS,
        Permission.MANAGE_USERS,
        # NOTE: No GENERATE / SIGN / REVOKE — admins cannot issue docs
        # NOTE: No edit_issued_document
    },

    Role.ISSUING_AUTHORITY: {
        Permission.READ_ALL_DOCUMENTS,
        Permission.UPLOAD_DOCUMENTS,
        Permission.GENERATE_DOCUMENT,
        Permission.DIGITALLY_SIGN,
        Permission.REVOKE_DOCUMENT,
        Permission.REISSUE_DOCUMENT,
        Permission.VERIFY_DOCUMENT,
        # NOTE: No edit_issued_document (not in any role — by design)
    },
}


def has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())


# ── Token extraction helper ───────────────────────────────────────────────────

async def _get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[User]:
    """Core token → User resolution, returns None on any failure."""
    if credentials is None:
        return None

    token = credentials.credentials
    try:
        payload = verify_access_token(token)
    except _jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired. Please refresh.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except _jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = db.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found.",
        )
    if user.status != AccountStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account is {user.status.value}.",
        )

    return user


# ── Public dependency functions ───────────────────────────────────────────────

async def require_auth(
    user: Optional[User] = Depends(_get_current_user_optional),
) -> User:
    """Require any authenticated user."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def optional_auth(
    user: Optional[User] = Depends(_get_current_user_optional),
) -> Optional[User]:
    """Return the authenticated user or None for unauthenticated requests."""
    return user


def require_role(*roles: Role):
    """
    FastAPI dependency factory.

    Usage
    -----
        @router.get("/admin", dependencies=[Depends(require_role(Role.SYSTEM_ADMIN))])
        async def admin_endpoint(): ...

        # or inject the user:
        @router.get("/admin")
        async def admin_endpoint(user: User = Depends(require_role(Role.SYSTEM_ADMIN))): ...
    """
    async def _check(user: User = Depends(require_auth)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Access denied. Required role(s): "
                    f"{', '.join(r.value for r in roles)}. "
                    f"Your role: {user.role.value}."
                ),
            )
        return user
    return _check


def require_permission(permission: Permission):
    """
    FastAPI dependency factory — check a specific permission.

    Usage
    -----
        @router.post("/sign", dependencies=[Depends(require_permission(Permission.DIGITALLY_SIGN))])
        async def sign_document(): ...
    """
    async def _check(user: User = Depends(require_auth)) -> User:
        if not has_permission(user.role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Permission denied: {permission.value}. "
                    f"Your role ({user.role.value}) does not have this permission."
                ),
            )
        return user
    return _check


def require_jurisdiction(jurisdiction: Optional[str] = None):
    """
    Dependency for Government Officials — enforces they can only access
    documents within their assigned jurisdiction.

    If jurisdiction is None, it is extracted from the query/path param
    by the caller; this dependency validates it against user.jurisdiction.
    """
    async def _check(user: User = Depends(require_role(Role.GOVERNMENT_OFFICIAL))) -> User:
        if jurisdiction and user.jurisdiction and user.jurisdiction != jurisdiction:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Jurisdiction mismatch. You are assigned to "
                    f"'{user.jurisdiction}', not '{jurisdiction}'."
                ),
            )
        return user
    return _check
