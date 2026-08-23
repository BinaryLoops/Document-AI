"""
auth/otp_handler.py — Phone OTP generation, delivery, validation, and lockout.

Flow (Citizen login)
--------------------
  1. POST /auth/login   →  issue_otp(user_id, phone) → returns otp_id
  2. [SMS sent to phone — in production replace _send_sms with real gateway]
  3. POST /auth/otp     →  verify_otp_code(otp_id, code) → bool

Security
--------
  - 6-digit cryptographically random code
  - SHA-256 hashed before storage (fast, safe for short-lived tokens)
  - TTL: OTP_TTL_SECONDS (default 300 = 5 min)
  - Max attempts: OTP_MAX_ATTEMPTS (default 5) before the record is burned
  - Constant-time comparison to prevent timing attacks
  - One active OTP per (user_id, purpose) — old ones are invalidated on reissue
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from auth.database import (
    get_latest_otp, get_otp, invalidate_user_otps, save_otp,
)
from auth.hashing import generate_otp_code, hash_otp, verify_otp
from auth.models import OTPRecord
from core.logging import get_logger

logger = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
OTP_TTL_SECONDS  = int(os.getenv("OTP_TTL_SECONDS",  "300"))   # 5 minutes
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_DIGITS       = int(os.getenv("OTP_DIGITS",       "6"))


# ── Issue ─────────────────────────────────────────────────────────────────────

def issue_otp(user_id: str, phone: str, purpose: str = "login") -> Tuple[str, str, Optional[str]]:
    """
    Generate a new OTP, persist it, and send it to the phone.

    Parameters
    ----------
    user_id : str   Target user
    phone   : str   Destination phone number (E.164 format)
    purpose : str   "login" | "phone_verify" | "password_reset"

    Returns
    -------
    (otp_id, masked_phone, dev_code) — dev_code is returned only in development
    """
    # Invalidate any pending OTPs for this (user, purpose) before issuing a new one
    invalidate_user_otps(user_id, purpose)

    code      = generate_otp_code(OTP_DIGITS)
    code_hash = hash_otp(code)
    expires   = datetime.now(timezone.utc) + timedelta(seconds=OTP_TTL_SECONDS)

    record = OTPRecord(
        user_id=user_id,
        phone=phone,
        otp_hash=code_hash,
        purpose=purpose,
        expires_at=expires,
    )
    save_otp(record)

    _send_sms(phone, code, purpose)

    masked = _mask_phone(phone)
    logger.info(
        "OTP issued: user=%s phone=%s otp_id=%s purpose=%s ttl=%ds",
        user_id, masked, record.otp_id, purpose, OTP_TTL_SECONDS,
    )
    dev_code = code if os.getenv("APP_ENV", "development").lower() in {
        "development", "dev", "testing", "test"
    } else None
    return record.otp_id, masked, dev_code


def _mask_phone(phone: str) -> str:
    """Return e.g. '+91XXXXXX3210' for log-safe display."""
    if len(phone) <= 4:
        return "****"
    return phone[:-4].replace(phone[:-4][-len(phone[:-4]):], "X" * len(phone[:-4])) + phone[-4:]


def _send_sms(phone: str, code: str, purpose: str) -> None:
    """
    SMS delivery.  In production wire this to your SMS gateway
    (Twilio, AWS SNS, MSG91, Fast2SMS, etc.).
    In development the code is printed to the server log.
    """
    env = os.getenv("APP_ENV", "development")
    if env in ("development", "dev", "testing", "test"):
        logger.info(
            "[DEV OTP] Phone=%s  Code=%s  Purpose=%s  (not sent — dev mode)",
            _mask_phone(phone), code, purpose,
        )
        return

    # Production: plug in your SMS gateway here
    # Example with Twilio:
    # from twilio.rest import Client
    # client = Client(TWILIO_SID, TWILIO_TOKEN)
    # client.messages.create(to=phone, from_=TWILIO_FROM, body=f"Your DocuMind OTP: {code}")
    logger.warning(
        "SMS gateway not configured — OTP for %s NOT delivered",
        _mask_phone(phone),
    )


# ── Verify ────────────────────────────────────────────────────────────────────

class OTPError(Exception):
    """Base OTP error — carries a user-safe message."""
    def __init__(self, message: str, code: str = "otp_error"):
        self.message = message
        self.code    = code
        super().__init__(message)


def verify_otp_code(otp_id: str, submitted_code: str) -> OTPRecord:
    """
    Validate a submitted OTP code against the stored record.

    Returns the OTPRecord on success.
    Raises OTPError on failure (expired, too many attempts, wrong code).
    """
    record = get_otp(otp_id)
    if record is None:
        raise OTPError("OTP not found or already used.", "otp_not_found")

    now = datetime.now(timezone.utc)

    # Already verified
    if record.verified:
        raise OTPError("OTP has already been used.", "otp_used")

    # Expired
    if record.expires_at and now > record.expires_at:
        raise OTPError(
            f"OTP has expired. Please request a new code.",
            "otp_expired",
        )

    # Too many attempts — burn the record
    if record.attempts >= OTP_MAX_ATTEMPTS:
        raise OTPError(
            f"Too many incorrect attempts. Please request a new OTP.",
            "otp_locked",
        )

    # Increment attempt counter before checking (prevents timing oracle)
    record.attempts += 1
    save_otp(record)

    # Constant-time comparison
    if not verify_otp(submitted_code.strip(), record.otp_hash):
        remaining = OTP_MAX_ATTEMPTS - record.attempts
        raise OTPError(
            f"Invalid OTP code. {remaining} attempt(s) remaining.",
            "otp_invalid",
        )

    # Mark verified
    record.verified    = True
    record.verified_at = now
    save_otp(record)

    logger.info(
        "OTP verified: otp_id=%s user=%s purpose=%s",
        otp_id, record.user_id, record.purpose,
    )
    return record
