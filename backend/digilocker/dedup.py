"""
digilocker/dedup.py — Duplicate document detection.

Two detection strategies:
  1. Content hash (SHA-256) — exact duplicate detection.
  2. Perceptual hash (pHash via imagehash) — near-duplicate detection for images.

Usage::

    detector = DuplicateDetector()
    is_dup, original_id = await detector.check(file_bytes, "image/png", db)
"""

from __future__ import annotations

import hashlib
import io
import logging
from typing import Optional, Tuple, TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from digilocker.database import DocumentDatabase


def compute_sha256(data: bytes) -> str:
    """Compute SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def compute_perceptual_hash(image_bytes: bytes) -> Optional[str]:
    """
    Compute perceptual hash (pHash) for an image.
    Returns hex string, or None if the image can't be processed.
    """
    try:
        import imagehash
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        phash = imagehash.phash(image)
        return str(phash)
    except ImportError:
        logger.debug("imagehash not installed — skipping perceptual hash")
        return None
    except Exception as e:
        logger.warning("Perceptual hash failed: %s", e)
        return None


class DuplicateDetector:
    """
    Detects duplicate documents using content hash + perceptual hash.

    Content hash catches exact duplicates (byte-identical files).
    Perceptual hash catches near-duplicates (resized, re-compressed images).
    """

    # Hamming distance threshold for perceptual hash similarity
    PHASH_THRESHOLD = 8

    async def check(
        self,
        file_bytes: bytes,
        mime_type: str,
        db: "DocumentDatabase",
    ) -> Tuple[bool, Optional[str]]:
        """
        Check whether a file is a duplicate.

        Args:
            file_bytes: Raw file content.
            mime_type:  MIME type of the file.
            db:         Database instance for querying existing hashes.

        Returns:
            (is_duplicate, duplicate_of_document_id)
        """
        file_hash = compute_sha256(file_bytes)

        # 1. Exact content-hash match
        existing_id = await db.find_by_hash(file_hash)
        if existing_id:
            logger.info(
                "Exact duplicate detected (hash=%s…) → document %s",
                file_hash[:12], existing_id,
            )
            return True, existing_id

        # 2. Perceptual hash for images
        if mime_type.startswith("image/"):
            phash = compute_perceptual_hash(file_bytes)
            if phash:
                similar_id = await db.find_similar_phash(phash, self.PHASH_THRESHOLD)
                if similar_id:
                    logger.info(
                        "Near-duplicate image detected (phash=%s) → document %s",
                        phash, similar_id,
                    )
                    return True, similar_id

        return False, None
