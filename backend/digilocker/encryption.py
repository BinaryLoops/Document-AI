"""
digilocker/encryption.py — AES-256 document encryption service.

Design:
  - Master key read from DIGILOCKER_MASTER_KEY env var (base64-encoded 32 bytes).
  - Per-document Data Encryption Key (DEK) is randomly generated.
  - DEK wraps the document via AES-256-GCM (authenticated encryption).
  - DEK itself is wrapped (encrypted) with the master key via AES-256-GCM.
  - Encrypted blob layout:  wrapped_dek_len(4B) | wrapped_dek | nonce(12B) | ciphertext | tag(16B)

This provides envelope encryption — compromising one document's DEK
does not compromise others.
"""

from __future__ import annotations

import base64
import binascii
import logging
import os
import struct
from typing import Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

# AES-256 key size
_KEY_SIZE = 32   # 256 bits
_NONCE_SIZE = 12  # 96 bits for GCM


class AES256Encryptor:
    """
    Envelope-encryption service using AES-256-GCM.

    Usage::

        encryptor = AES256Encryptor()
        encrypted, key_blob = encryptor.encrypt(plaintext_bytes)
        decrypted = encryptor.decrypt(encrypted, key_blob)
        assert decrypted == plaintext_bytes
    """

    def __init__(self, master_key: str | None = None):
        """
        Args:
            master_key: Base64-encoded 32-byte master key.
                        Falls back to DIGILOCKER_MASTER_KEY env var.
                        If neither is set, a random key is generated (dev mode).
        """
        raw = master_key or os.environ.get("DIGILOCKER_MASTER_KEY")
        if raw:
            try:
                self._master_key = base64.urlsafe_b64decode(raw)
            except (binascii.Error, ValueError) as e:
                raise ValueError(
                    "DIGILOCKER_MASTER_KEY is not valid base64. It must be a "
                    "urlsafe-base64-encoded 32-byte key, e.g. generate one with: "
                    "python -c \"import base64, os; "
                    "print(base64.urlsafe_b64encode(os.urandom(32)).decode())\""
                ) from e
            if len(self._master_key) != _KEY_SIZE:
                raise ValueError(
                    f"Master key must be {_KEY_SIZE} bytes after base64 decoding "
                    f"(got {len(self._master_key)}). Generate one with: "
                    "python -c \"import base64, os; "
                    "print(base64.urlsafe_b64encode(os.urandom(32)).decode())\""
                )
            logger.info("AES-256 encryptor initialised with provided master key")
        else:
            self._master_key = os.urandom(_KEY_SIZE)
            logger.warning(
                "No DIGILOCKER_MASTER_KEY set — generated random master key. "
                "Data will NOT survive restarts. Set the env var for persistence."
            )

    # ── Public API ───────────────────────────────────────────────────────

    def encrypt(self, plaintext: bytes) -> Tuple[bytes, bytes]:
        """
        Encrypt data with a fresh per-document DEK.

        Returns:
            (ciphertext, wrapped_dek)
            Both must be stored — ciphertext in vault, wrapped_dek alongside.
        """
        # 1. Generate random DEK
        dek = os.urandom(_KEY_SIZE)

        # 2. Encrypt plaintext with DEK
        nonce = os.urandom(_NONCE_SIZE)
        aesgcm = AESGCM(dek)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        # ciphertext includes the 16-byte GCM tag appended by cryptography

        encrypted_blob = nonce + ciphertext  # 12 + len(plaintext) + 16

        # 3. Wrap DEK with master key
        wrapped_dek = self._wrap_key(dek)

        return encrypted_blob, wrapped_dek

    def decrypt(self, encrypted_blob: bytes, wrapped_dek: bytes) -> bytes:
        """
        Decrypt data given the encrypted blob and its wrapped DEK.
        """
        # 1. Unwrap DEK
        dek = self._unwrap_key(wrapped_dek)

        # 2. Split nonce and ciphertext
        nonce = encrypted_blob[:_NONCE_SIZE]
        ciphertext = encrypted_blob[_NONCE_SIZE:]

        # 3. Decrypt
        aesgcm = AESGCM(dek)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return plaintext

    # ── Key wrapping ─────────────────────────────────────────────────────

    def _wrap_key(self, dek: bytes) -> bytes:
        """Encrypt the DEK with the master key (AES-256-GCM)."""
        nonce = os.urandom(_NONCE_SIZE)
        aesgcm = AESGCM(self._master_key)
        wrapped = aesgcm.encrypt(nonce, dek, None)
        return nonce + wrapped   # 12 + 32 + 16 = 60 bytes

    def _unwrap_key(self, wrapped_dek: bytes) -> bytes:
        """Decrypt the DEK with the master key."""
        nonce = wrapped_dek[:_NONCE_SIZE]
        ciphertext = wrapped_dek[_NONCE_SIZE:]
        aesgcm = AESGCM(self._master_key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    # ── Utility ──────────────────────────────────────────────────────────

    @staticmethod
    def generate_master_key() -> str:
        """Generate a new random master key and return as base64 string."""
        key = os.urandom(_KEY_SIZE)
        return base64.urlsafe_b64encode(key).decode()
