"""
generation/qr_generator.py — QR code generation for document verification.

Each QR code embeds a JSON payload containing:
  - doc_id        (UUID)
  - document_number
  - document_type
  - applicant_name
  - issued_at     (ISO-8601)
  - hash          (SHA-256 of the payload JSON, for tamper detection)
  - verify_url    (public verification endpoint URL)

The QR is rendered as a PIL Image and also returned as PNG bytes so it
can be embedded directly into the ReportLab PDF canvas.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from datetime import datetime, timezone
from typing import Tuple

import qrcode
from qrcode.image.pil import PilImage
from PIL import Image

from core.logging import get_logger

logger = get_logger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
_BASE_URL = os.getenv("DOC_VERIFY_BASE_URL", "http://localhost:8000")
_VERIFY_PATH = "/generate/verify/"


def build_qr_payload(
    doc_id:          str,
    document_number: str,
    document_type:   str,
    applicant_name:  str,
    issued_at:       datetime,
) -> Tuple[str, str, str]:
    """
    Build the QR payload, compute its hash, and return the verification URL.

    Returns
    -------
    (verify_url, payload_json, payload_hash)
    """
    verify_url = f"{_BASE_URL}{_VERIFY_PATH}{document_number}"

    payload: dict = {
        "doc_id":          doc_id,
        "document_number": document_number,
        "document_type":   document_type,
        "applicant_name":  applicant_name,
        "issued_at":       issued_at.isoformat(),
        "verify_url":      verify_url,
    }

    # Deterministic JSON for stable hash
    payload_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

    # Add hash to payload (QR scanner can verify on-device)
    payload["hash"] = payload_hash
    full_json = json.dumps(payload, sort_keys=True, ensure_ascii=False)

    return verify_url, full_json, payload_hash


def generate_qr_image(
    payload_json: str,
    box_size:     int = 6,
    border:       int = 2,
    size_px:      int = 200,
) -> Tuple[Image.Image, bytes]:
    """
    Render a QR code for the given JSON payload.

    Parameters
    ----------
    payload_json : the JSON string to encode
    box_size     : pixels per QR module
    border       : quiet-zone modules
    size_px      : final image size (thumbnail); QR is scaled to fit

    Returns
    -------
    (PIL Image, PNG bytes)
    """
    qr = qrcode.QRCode(
        version=None,                          # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_H,  # 30% recovery
        box_size=box_size,
        border=border,
    )
    qr.add_data(payload_json)
    qr.make(fit=True)

    qr_img: PilImage = qr.make_image(fill_color="black", back_color="white")
    pil_img: Image.Image = qr_img.get_image()   # underlying PIL Image

    # Resize to requested square
    if size_px and size_px > 0:
        pil_img = pil_img.resize((size_px, size_px), Image.LANCZOS)

    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    return pil_img, buf.read()


def make_document_qr(
    doc_id:          str,
    document_number: str,
    document_type:   str,
    applicant_name:  str,
    issued_at:       datetime,
    size_px:         int = 200,
) -> Tuple[str, str, bytes]:
    """
    End-to-end helper: build payload → generate QR image.

    Returns
    -------
    (verify_url, payload_hash, qr_png_bytes)
    """
    verify_url, payload_json, payload_hash = build_qr_payload(
        doc_id=doc_id,
        document_number=document_number,
        document_type=document_type,
        applicant_name=applicant_name,
        issued_at=issued_at,
    )
    _, qr_png = generate_qr_image(payload_json, size_px=size_px)
    logger.debug(
        "QR generated: doc=%s hash=%s", document_number, payload_hash[:16]
    )
    return verify_url, payload_hash, qr_png
