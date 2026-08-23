"""
auth/mfa.py — TOTP-based MFA for Government Officials, System Admins,
              and Issuing Authorities.

Design
------
  - Standard TOTP (RFC 6238), 30-second window, SHA-1 (pyotp default)
  - Compatible with Google Authenticator, Authy, Microsoft Authenticator
  - Setup returns a provisioning URI the client renders as a QR code
  - 8 single-use backup codes generated at setup; each is bcrypt-hashed
  - One window of drift (30 s) tolerated on either side
"""

from __future__ import annotations

import os
import secrets
from typing import List, Tuple

import pyotp

from auth.hashing import generate_backup_code, hash_backup_code, verify_backup_code_hash
from auth.models import Role, User
from core.logging import get_logger

logger = get_logger(__name__)

_APP_NAME   = os.getenv("MFA_APP_NAME", "DocuMind AI")
_BACKUP_N   = 8          # number of backup codes generated at setup
_DRIFT      = 1          # ±1 window = ±30 seconds tolerance


# ── Roles that MUST complete MFA ─────────────────────────────────────────────
MFA_REQUIRED_ROLES = {
    Role.GOVERNMENT_OFFICIAL,
    Role.SYSTEM_ADMIN,
    Role.ISSUING_AUTHORITY,
}


def mfa_required_for_role(role: Role) -> bool:
    return role in MFA_REQUIRED_ROLES


# ── Setup ─────────────────────────────────────────────────────────────────────

def setup_mfa(user: User) -> Tuple[str, str, List[str]]:
    """
    Generate a fresh TOTP secret and backup codes for a user.

    Does NOT save to the database — the caller must call auth.database.save_user()
    after setting user.mfa_secret, user.mfa_backup_codes, user.mfa_enabled.

    Returns
    -------
    (secret_b32, provisioning_uri, plain_backup_codes)

    plain_backup_codes must be shown to the user ONCE and then hashed.
    """
    secret = pyotp.random_base32()
    totp   = pyotp.TOTP(secret)

    # Build a human-readable label
    label  = user.employee_id or user.department_code or user.user_id
    uri    = totp.provisioning_uri(name=label, issuer_name=_APP_NAME)

    plain_codes = [generate_backup_code() for _ in range(_BACKUP_N)]

    logger.info("MFA setup initiated for user=%s role=%s", user.user_id, user.role.value)
    return secret, uri, plain_codes


def hash_backup_codes(plain_codes: list) -> list:
    """Hash each backup code for storage."""
    return [hash_backup_code(c) for c in plain_codes]


# ── Verification ──────────────────────────────────────────────────────────────

def verify_totp(user: User, code: str) -> bool:
    """
    Verify a 6-digit TOTP code against the user's stored secret.
    Allows ±1 window drift.
    """
    if not user.mfa_secret:
        return False
    try:
        totp = pyotp.TOTP(user.mfa_secret)
        return totp.verify(code.strip(), valid_window=_DRIFT)
    except Exception as e:
        logger.warning("TOTP verify error for user=%s: %s", user.user_id, e)
        return False


def verify_backup_code(user: User, submitted: str) -> Tuple[bool, List[str]]:
    """
    Check submitted code against stored backup code hashes.
    Returns (matched, updated_backup_hashes) — the matched code is removed.
    """
    submitted = submitted.strip().upper()
    updated   = []
    matched   = False
    for stored_hash in user.mfa_backup_codes:
        if not matched and verify_backup_code_hash(submitted, stored_hash):
            matched = True   # consume — do NOT add back
        else:
            updated.append(stored_hash)

    if matched:
        logger.info(
            "Backup code used: user=%s codes_remaining=%d",
            user.user_id, len(updated),
        )
    return matched, updated
