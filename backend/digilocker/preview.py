"""
digilocker/preview.py — Document preview & thumbnail generation.

Generates:
  - Preview image (max 800px wide)
  - Thumbnail image (max 200px wide)

Supports:
  - PDF   → render first page via PyMuPDF
  - Images (JPG/PNG) → resize
  - DOCX  → extract first page text rendered as simple image
"""

from __future__ import annotations

import io
import logging
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

PREVIEW_MAX_WIDTH = 800
THUMB_MAX_WIDTH = 200


class PreviewGenerator:
    """Generate preview and thumbnail images for documents."""

    def generate(
        self,
        file_bytes: bytes,
        mime_type: str,
        filename: str = "",
    ) -> Tuple[Optional[bytes], Optional[bytes]]:
        """
        Generate preview and thumbnail from raw file bytes.

        Returns:
            (preview_png_bytes, thumbnail_png_bytes)
            Either may be None if generation fails.
        """
        try:
            if mime_type == "application/pdf":
                return self._from_pdf(file_bytes)
            elif mime_type.startswith("image/"):
                return self._from_image(file_bytes)
            elif mime_type in (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword",
            ):
                return self._from_docx(file_bytes, filename)
            else:
                logger.info("No preview generator for MIME type: %s", mime_type)
                return None, None
        except Exception as e:
            logger.error("Preview generation failed for '%s': %s", filename, e)
            return None, None

    # ── PDF ──────────────────────────────────────────────────────────────

    def _from_pdf(self, file_bytes: bytes) -> Tuple[Optional[bytes], Optional[bytes]]:
        """Render the first page of a PDF as an image."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("PyMuPDF not installed — cannot generate PDF previews")
            return None, None

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        if len(doc) == 0:
            doc.close()
            return None, None

        page = doc[0]
        # Render at 2x for decent quality
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        img_bytes = pix.tobytes("png")
        doc.close()

        image = Image.open(io.BytesIO(img_bytes))
        preview = self._resize(image, PREVIEW_MAX_WIDTH)
        thumb = self._resize(image, THUMB_MAX_WIDTH)

        return self._to_png(preview), self._to_png(thumb)

    # ── Images ───────────────────────────────────────────────────────────

    def _from_image(self, file_bytes: bytes) -> Tuple[Optional[bytes], Optional[bytes]]:
        """Resize an image for preview and thumbnail."""
        image = Image.open(io.BytesIO(file_bytes))
        # Convert RGBA/P to RGB for consistent PNG output
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")

        preview = self._resize(image, PREVIEW_MAX_WIDTH)
        thumb = self._resize(image, THUMB_MAX_WIDTH)

        return self._to_png(preview), self._to_png(thumb)

    # ── DOCX ─────────────────────────────────────────────────────────────

    def _from_docx(
        self, file_bytes: bytes, filename: str
    ) -> Tuple[Optional[bytes], Optional[bytes]]:
        """Extract text from DOCX and render as a simple preview image."""
        try:
            import docx as python_docx
        except ImportError:
            logger.warning("python-docx not installed — cannot preview DOCX")
            return None, None

        doc = python_docx.Document(io.BytesIO(file_bytes))
        text_lines = []
        for para in doc.paragraphs[:30]:  # first 30 paragraphs
            if para.text.strip():
                text_lines.append(para.text.strip())

        if not text_lines:
            return None, None

        # Render text to image
        preview_text = "\n".join(text_lines[:20])
        image = self._text_to_image(preview_text, width=PREVIEW_MAX_WIDTH)
        preview = self._to_png(image)

        thumb_image = self._resize(image, THUMB_MAX_WIDTH)
        thumb = self._to_png(thumb_image)

        return preview, thumb

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _resize(image: Image.Image, max_width: int) -> Image.Image:
        """Resize image proportionally so width <= max_width."""
        if image.width <= max_width:
            return image.copy()
        ratio = max_width / image.width
        new_height = int(image.height * ratio)
        return image.resize((max_width, new_height), Image.LANCZOS)

    @staticmethod
    def _to_png(image: Image.Image) -> bytes:
        """Convert PIL Image to PNG bytes."""
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return buf.getvalue()

    @staticmethod
    def _text_to_image(
        text: str,
        width: int = 800,
        padding: int = 20,
        line_height: int = 22,
        bg_color: str = "#FFFFFF",
        text_color: str = "#1A1A1A",
    ) -> Image.Image:
        """Render text lines to a simple image."""
        lines = text.split("\n")
        height = padding * 2 + len(lines) * line_height
        height = max(height, 100)

        image = Image.new("RGB", (width, height), bg_color)
        draw = ImageDraw.Draw(image)

        # Use default font (no external font files required)
        try:
            font = ImageFont.truetype("arial.ttf", 14)
        except (OSError, IOError):
            font = ImageFont.load_default()

        y = padding
        for line in lines:
            # Truncate very long lines
            if len(line) > 100:
                line = line[:97] + "..."
            draw.text((padding, y), line, fill=text_color, font=font)
            y += line_height

        return image
