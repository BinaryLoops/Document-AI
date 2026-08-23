"""
digilocker/vault.py — Encrypted file storage on local filesystem.

Directory layout::

    vault/
    └── 2026/
        └── 08/
            └── a1b2c3d4/           ← first 8 chars of document_id
                ├── a1b2c3d4-...-ef.enc      ← encrypted document
                ├── a1b2c3d4-...-ef.dek      ← wrapped DEK
                ├── a1b2c3d4-...-ef.preview  ← preview image (unencrypted)
                └── a1b2c3d4-...-ef.thumb    ← thumbnail (unencrypted)

All reads/writes go through this class — no direct filesystem access elsewhere.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_DEFAULT_VAULT_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vault")


class FileVault:
    """
    Local filesystem vault for encrypted document blobs.

    Usage::

        vault = FileVault()
        ref = vault.store("doc-uuid", encrypted_bytes, wrapped_dek)
        enc_bytes, dek_bytes = vault.retrieve("doc-uuid", ref)
    """

    def __init__(self, vault_root: str | None = None):
        self.root = Path(vault_root or os.environ.get("VAULT_ROOT", _DEFAULT_VAULT_ROOT))
        self.root.mkdir(parents=True, exist_ok=True)
        logger.info("FileVault initialised at %s", self.root)

    # ── Store ────────────────────────────────────────────────────────────

    def store(
        self,
        document_id: str,
        encrypted_bytes: bytes,
        wrapped_dek: bytes,
    ) -> str:
        """
        Write encrypted blob + wrapped DEK to vault.

        Returns:
            vault_ref — relative path used to retrieve later.
        """
        dir_path = self._doc_dir(document_id)
        dir_path.mkdir(parents=True, exist_ok=True)

        enc_path = dir_path / f"{document_id}.enc"
        dek_path = dir_path / f"{document_id}.dek"

        enc_path.write_bytes(encrypted_bytes)
        dek_path.write_bytes(wrapped_dek)

        vault_ref = str(enc_path.relative_to(self.root))
        logger.info(
            "Stored encrypted document %s (%d bytes) → %s",
            document_id, len(encrypted_bytes), vault_ref,
        )
        return vault_ref

    # ── Retrieve ─────────────────────────────────────────────────────────

    def retrieve(self, document_id: str, vault_ref: str) -> Tuple[bytes, bytes]:
        """
        Read encrypted blob + wrapped DEK from vault.

        Returns:
            (encrypted_bytes, wrapped_dek)

        Raises:
            FileNotFoundError: if the vault reference doesn't exist.
        """
        enc_path = self.root / vault_ref
        dek_path = enc_path.with_suffix(".dek")

        if not enc_path.exists():
            raise FileNotFoundError(f"Vault blob not found: {vault_ref}")
        if not dek_path.exists():
            raise FileNotFoundError(f"Vault DEK not found for: {vault_ref}")

        return enc_path.read_bytes(), dek_path.read_bytes()

    # ── Preview / Thumbnail ──────────────────────────────────────────────

    def store_preview(self, document_id: str, preview_bytes: bytes) -> str:
        """Store a preview image (unencrypted) and return the vault ref."""
        dir_path = self._doc_dir(document_id)
        dir_path.mkdir(parents=True, exist_ok=True)
        path = dir_path / f"{document_id}.preview"
        path.write_bytes(preview_bytes)
        return str(path.relative_to(self.root))

    def store_thumbnail(self, document_id: str, thumb_bytes: bytes) -> str:
        """Store a thumbnail image (unencrypted) and return the vault ref."""
        dir_path = self._doc_dir(document_id)
        dir_path.mkdir(parents=True, exist_ok=True)
        path = dir_path / f"{document_id}.thumb"
        path.write_bytes(thumb_bytes)
        return str(path.relative_to(self.root))

    def retrieve_preview(self, document_id: str) -> Optional[bytes]:
        """Read preview bytes, or None if not available."""
        path = self._doc_dir(document_id) / f"{document_id}.preview"
        return path.read_bytes() if path.exists() else None

    def retrieve_thumbnail(self, document_id: str) -> Optional[bytes]:
        """Read thumbnail bytes, or None if not available."""
        path = self._doc_dir(document_id) / f"{document_id}.thumb"
        return path.read_bytes() if path.exists() else None

    # ── Helpers ──────────────────────────────────────────────────────────

    def _doc_dir(self, document_id: str) -> Path:
        """Build the directory path for a document: vault/YYYY/MM/id_prefix/"""
        now = datetime.now(timezone.utc)
        return self.root / str(now.year) / f"{now.month:02d}" / document_id[:8]

    def exists(self, vault_ref: str) -> bool:
        return (self.root / vault_ref).exists()
