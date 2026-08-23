"""
auth/hashing.py — Cryptographic helpers.

Passlib 1.7.4 is incompatible with bcrypt>=4.0 due to internal API changes.
We bypass passlib entirely and call the bcrypt package directly.

Functions
---------
  hash_password(plain)           → bcrypt hash string
  verify_password(plain, hashed) → bool
  hash_aadhaar(number)           → deterministic HMAC-SHA256 hex
  verify_aadhaar(number, stored) → bool  (constant-time)
  hash_token(raw)                → SHA-256 hex  (refresh token storage)
  verify_token_hash(raw, stored) → bool
  hash_otp(otp_code)             → SHA-256 hex  (fast, sufficient for short TTL)
  verify_otp(otp_code, hashed)   → bool
  generate_otp_code(digits)      → str
  generate_backup_code()         → str
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

import bcrypt as _bcrypt

from core.logging import get_logger

logger = get_logger(__name__)

# ── bcrypt settings ───────────────────────────────────────────────────────────
_BCRYPT_ROUNDS = 12     # OWASP minimum

# ── Aadhaar HMAC key ─────────────────────────────────────────────────────────
_AADHAAR_KEY_ENV = "AADHAAR_HMAC_KEY"

def _aadhaar_key() -> bytes:
    key = os.getenv(_AADHAAR_KEY_ENV, "")
    if not key:
        logger.warning(
            "AADHAAR_HMAC_KEY not set -- using insecure dev key. "
            "Set a 32-byte random secret in production."
        )
        key = "dev-aadhaar-hmac-key-change-in-prod"
    return key.encode()


# ── Password hashing (bcrypt direct) ─────────────────────────────────────────

def hash_password(plain: str) -> str:
    """
    Return a bcrypt hash string for the plain-text password.
    Truncates to 72 bytes (bcrypt spec limit).
    """
    # bcrypt has a hard 72-byte limit
    pw_bytes = plain.encode("utf-8")[:72]
    salt     = _bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    hashed   = _bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt comparison. Returns False on any error."""
    try:
        pw_bytes = plain.encode("utf-8")[:72]
        return _bcrypt.checkpw(pw_bytes, hashed.encode("utf-8"))
    except Exception:
        return False


# ── Aadhaar hashing (HMAC-SHA256) ────────────────────────────────────────────

def hash_aadhaar(aadhaar_number: str) -> str:
    """
    HMAC-SHA256 of the Aadhaar number.

    Using HMAC (keyed hash) so we can look up a user by their Aadhaar at
    login time.  The HMAC key is stored securely in the environment.
    """
    cleaned = aadhaar_number.replace(" ", "").strip()
    digest  = hmac.new(_aadhaar_key(), cleaned.encode(), hashlib.sha256).hexdigest()
    return digest


def verify_aadhaar(aadhaar_number: str, stored_hash: str) -> bool:
    """Constant-time comparison of Aadhaar hash."""
    computed = hash_aadhaar(aadhaar_number)
    return hmac.compare_digest(computed, stored_hash)


# ── Token hashing (refresh token) ────────────────────────────────────────────

def hash_token(raw_token: str) -> str:
    """SHA-256 hex of a raw token — used for refresh token storage."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def verify_token_hash(raw_token: str, stored_hash: str) -> bool:
    """Constant-time compare of token hash."""
    computed = hash_token(raw_token)
    return hmac.compare_digest(computed, stored_hash)


# ── OTP hashing (SHA-256 — fast, sufficient for 5-min TTL) ───────────────────

def hash_otp(otp_code: str) -> str:
    """SHA-256 hash of a 6-digit OTP code (fast, OK for short-lived tokens)."""
    return hashlib.sha256(otp_code.strip().encode()).hexdigest()


def verify_otp(otp_code: str, hashed: str) -> bool:
    """Constant-time comparison of OTP hash."""
    computed = hash_otp(otp_code)
    return hmac.compare_digest(computed, hashed)


# ── Backup code hashing ───────────────────────────────────────────────────────

def hash_backup_code(plain: str) -> str:
    """SHA-256 hash of a backup code."""
    return hashlib.sha256(plain.strip().upper().encode()).hexdigest()


def verify_backup_code_hash(plain: str, stored: str) -> bool:
    computed = hash_backup_code(plain)
    return hmac.compare_digest(computed, stored)


# ── Secure random helpers ─────────────────────────────────────────────────────

def generate_otp_code(digits: int = 6) -> str:
    """Cryptographically secure N-digit OTP string."""
    return "".join(str(secrets.randbelow(10)) for _ in range(digits))


def generate_backup_code() -> str:
    """8-char alphanumeric backup code (uppercase, no ambiguous chars)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(8))
