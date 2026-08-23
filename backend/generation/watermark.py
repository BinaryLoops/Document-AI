"""
generation/watermark.py — Diagonal text watermark + department stamp overlay.

Generates a transparent RGBA PIL Image that ReportLab draws as the topmost
layer on every page, so it cannot be cropped off by splitting the PDF.

Two overlays
------------
  1. Diagonal watermark text — large, semi-transparent, repeated pattern.
     e.g. "OFFICIAL", "DRAFT", "REVOKED", "SPECIMEN"

  2. Department stamp circle — bottom-right corner, mimics an ink stamp.
"""

from __future__ import annotations

import io
import math
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from generation.models import WatermarkType
from core.logging import get_logger

logger = get_logger(__name__)

# ── Colour map ────────────────────────────────────────────────────────────────
_WATERMARK_COLOURS: dict[str, Tuple[int, int, int, int]] = {
    WatermarkType.OFFICIAL.value: (0,   100, 0,   45),   # dark green, 18 % opacity
    WatermarkType.DRAFT.value:    (180, 0,   0,   55),   # dark red,   22 %
    WatermarkType.REVOKED.value:  (100, 0,   0,   80),   # deep red,   31 %
    WatermarkType.SPECIMEN.value: (0,   0,   180, 55),   # blue,       22 %
}

_STAMP_COLOURS: dict[str, Tuple[int, int, int, int]] = {
    WatermarkType.OFFICIAL.value: (0,   100, 0,   160),
    WatermarkType.DRAFT.value:    (180, 0,   0,   160),
    WatermarkType.REVOKED.value:  (150, 0,   0,   200),
    WatermarkType.SPECIMEN.value: (0,   0,   180, 160),
}


def _get_font(size: int) -> ImageFont.ImageFont:
    """Try to load a bold system font; fall back to PIL default."""
    candidates = [
        "arialbd.ttf", "Arial_Bold.ttf",
        "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf",
    ]
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def build_watermark_image(
    page_width_px:  int,
    page_height_px: int,
    watermark_type: WatermarkType = WatermarkType.OFFICIAL,
    text:           Optional[str] = None,
) -> bytes:
    """
    Build a full-page transparent watermark PNG.

    Parameters
    ----------
    page_width_px / page_height_px : dimensions of the PDF page in pixels
    watermark_type : controls colour and default text
    text : override text (defaults to WatermarkType value)

    Returns
    -------
    PNG bytes of an RGBA image the same size as the page.
    """
    label  = text or watermark_type.value
    colour = _WATERMARK_COLOURS.get(watermark_type.value, (128, 128, 128, 45))

    img  = Image.new("RGBA", (page_width_px, page_height_px), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # ── Diagonal tiled text ───────────────────────────────────────────────
    font_size = max(48, page_width_px // 10)
    font      = _get_font(font_size)
    angle     = -35

    # Build a small tile with the text
    try:
        bbox = font.getbbox(label)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        tw, th = font.getsize(label)  # PIL < 10

    tile_w = tw + 80
    tile_h = th + 60
    tile   = Image.new("RGBA", (tile_w, tile_h), (255, 255, 255, 0))
    td     = ImageDraw.Draw(tile)
    td.text((40, 30), label, font=font, fill=colour)

    # Rotate tile
    rotated = tile.rotate(angle, expand=True, resample=Image.BICUBIC)

    # Tile across the full page
    rw, rh = rotated.size
    for y in range(-rh, page_height_px + rh, rh + 20):
        for x in range(-rw, page_width_px + rw, rw + 20):
            img.alpha_composite(rotated, dest=(x, y))

    # ── Department stamp (circle, bottom-right) ───────────────────────────
    _draw_stamp(draw, img.size, watermark_type)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def _draw_stamp(
    draw:       ImageDraw.ImageDraw,
    page_size:  Tuple[int, int],
    wm_type:    WatermarkType,
    dept_name:  str = "Government of India",
) -> None:
    """Draw a circular department stamp in the bottom-right corner."""
    pw, ph    = page_size
    stamp_r   = min(pw, ph) // 10          # radius
    cx        = pw - stamp_r - 20
    cy        = ph - stamp_r - 20
    colour    = _STAMP_COLOURS.get(wm_type.value, (0, 100, 0, 160))
    outline_w = max(2, stamp_r // 18)

    # Outer circle
    draw.ellipse(
        [cx - stamp_r, cy - stamp_r, cx + stamp_r, cy + stamp_r],
        outline=colour, width=outline_w,
    )
    # Inner circle
    inner_r = stamp_r - outline_w * 3
    draw.ellipse(
        [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
        outline=colour, width=1,
    )
    # Centre text
    small_font = _get_font(max(10, stamp_r // 4))
    draw.text((cx, cy - stamp_r // 6), "INDIA", fill=colour,
              font=small_font, anchor="mm" if hasattr(draw, "_image") else "la")
    draw.text((cx, cy + stamp_r // 6), wm_type.value, fill=colour,
              font=small_font, anchor="mm" if hasattr(draw, "_image") else "la")


def watermark_for_page(
    page_width_pt:  float,
    page_height_pt: float,
    watermark_type: WatermarkType = WatermarkType.OFFICIAL,
    dpi:            int = 150,
) -> bytes:
    """
    Convenience wrapper that converts ReportLab point dimensions → pixels.

    Parameters
    ----------
    page_width_pt / page_height_pt : ReportLab page size in points (1pt = 1/72 inch)
    dpi : render resolution (150 is sufficient for watermarks)

    Returns PNG bytes.
    """
    factor = dpi / 72.0
    pw = max(1, int(page_width_pt  * factor))
    ph = max(1, int(page_height_pt * factor))
    return build_watermark_image(pw, ph, watermark_type)
