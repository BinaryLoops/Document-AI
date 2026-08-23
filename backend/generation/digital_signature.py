"""
generation/digital_signature.py — RSA-2048 digital signing for generated PDFs.

Design
------
  - RSA-2048 key pair generated once and persisted to disk as PEM files.
  - Document signature = RSA-PKCS1v15 over SHA-256 hash of PDF bytes.
  - Signature stored as base64 string in GeneratedDocument.signature_value.
  - Verification uses the stored public key — works offline.
  - Key paths configurable via GEN_PRIVATE_KEY_PATH / GEN_PUBLIC_KEY_PATH env vars.

Usage
-----
    from generation.digital_signature import sign_pdf_bytes, verify_signature, get_public_key_pem

    sig_hex, sig_b64 = sign_pdf_bytes(pdf_bytes)        # returns (hash_hex, sig_b64)
    ok               = verify_signature(pdf_bytes, sig_b64)
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from typing import Tuple

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

from core.logging import get_logger

logger = get_logger(__name__)

# ── Key paths ─────────────────────────────────────────────────────────────────
_KEY_DIR      = Path(os.getenv("GEN_KEY_DIR",         "gen_keys"))
_PRIV_PATH    = Path(os.getenv("GEN_PRIVATE_KEY_PATH", str(_KEY_DIR / "private.pem")))
_PUB_PATH     = Path(os.getenv("GEN_PUBLIC_KEY_PATH",  str(_KEY_DIR / "public.pem")))

# ── In-memory key cache ───────────────────────────────────────────────────────
_private_key: RSAPrivateKey | None = None
_public_key:  RSAPublicKey  | None = None


def _ensure_keys() -> Tuple[RSAPrivateKey, RSAPublicKey]:
    """Load keys from disk; generate and save if they don't exist."""
    global _private_key, _public_key

    if _private_key and _public_key:
        return _private_key, _public_key

    if _PRIV_PATH.exists() and _PUB_PATH.exists():
        # Load existing
        _private_key = serialization.load_pem_private_key(
            _PRIV_PATH.read_bytes(), password=None, backend=default_backend()
        )
        _public_key = serialization.load_pem_public_key(
            _PUB_PATH.read_bytes(), backend=default_backend()
        )
        logger.info("Loaded RSA key pair from %s", _KEY_DIR)
    else:
        # Generate new RSA-2048 key pair
        logger.info("Generating new RSA-2048 key pair in %s …", _KEY_DIR)
        _KEY_DIR.mkdir(parents=True, exist_ok=True)

        _private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )
        _public_key = _private_key.public_key()

        # Persist
        _PRIV_PATH.write_bytes(
            _private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )
        _PUB_PATH.write_bytes(
            _public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
        logger.info("RSA key pair generated and saved.")

    return _private_key, _public_key


def sign_pdf_bytes(pdf_bytes: bytes) -> Tuple[str, str]:
    """
    Sign the PDF bytes with the private key.

    Returns
    -------
    (sha256_hex, signature_b64)
        sha256_hex    — hex SHA-256 digest of the PDF (stored as signature_hash)
        signature_b64 — base64 RSA-PKCS1v15 signature (stored as signature_value)
    """
    private_key, _ = _ensure_keys()

    sha256_hex = hashlib.sha256(pdf_bytes).hexdigest()

    sig_bytes = private_key.sign(
        pdf_bytes,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    sig_b64 = base64.b64encode(sig_bytes).decode("ascii")

    logger.debug("PDF signed: sha256=%s sig_len=%d", sha256_hex[:16], len(sig_bytes))
    return sha256_hex, sig_b64


def verify_signature(pdf_bytes: bytes, signature_b64: str) -> bool:
    """
    Verify a base64 signature against PDF bytes using the stored public key.

    Returns True if valid, False otherwise (never raises).
    """
    try:
        _, public_key = _ensure_keys()
        sig_bytes = base64.b64decode(signature_b64)
        public_key.verify(
            sig_bytes,
            pdf_bytes,
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception as e:
        logger.warning("Signature verification failed: %s", e)
        return False


def get_public_key_pem() -> str:
    """Return the public key as a PEM string (safe to expose in API)."""
    _, public_key = _ensure_keys()
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def get_key_fingerprint() -> str:
    """Return a short fingerprint of the public key for display."""
    pem = get_public_key_pem()
    digest = hashlib.sha256(pem.encode()).hexdigest()
    return ":".join(digest[i:i+2] for i in range(0, 16, 2))
