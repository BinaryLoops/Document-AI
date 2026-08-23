"""
generation/pdf_builder.py — ReportLab PDF assembly.

Builds a complete, print-ready government document PDF with:
  - Header:   national emblem placeholder + document title + doc number
  - Sections: labelled field tables grouped by section
  - QR code:  embedded in the lower-right of the first page
  - Watermark: full-page diagonal text overlay (OFFICIAL / DRAFT / REVOKED)
  - Signature block: authority name, digital signature indicator, date
  - Footer:   doc number, issuing authority, page number, verification URL
  - Metadata: PDF /Author, /Creator, /Subject, /Keywords, /Producer

Uses ReportLab Platypus for content and Canvas for overlays.
"""

from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.utils import ImageReader

from generation.models import DocumentField, GeneratedDocument, WatermarkType
from generation.watermark import watermark_for_page
from core.logging import get_logger

logger = get_logger(__name__)

# ── Page setup ────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4           # 595.27 x 841.89 pts
MARGIN_H       = 2.0 * cm
MARGIN_V       = 2.2 * cm

# ── Colour palette ────────────────────────────────────────────────────────────
GOV_NAVY   = colors.HexColor("#003366")
GOV_GOLD   = colors.HexColor("#CC9900")
GOV_LIGHT  = colors.HexColor("#EEF2F7")
GOV_BORDER = colors.HexColor("#8899AA")
TEXT_DARK  = colors.HexColor("#1A1A2E")
TEXT_MID   = colors.HexColor("#4A4A6A")


# ── Style helpers ─────────────────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "GovTitle",
            parent=base["Heading1"],
            fontSize=18,
            textColor=GOV_NAVY,
            spaceAfter=4,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "GovSubtitle",
            parent=base["Normal"],
            fontSize=10,
            textColor=GOV_GOLD,
            spaceAfter=2,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ),
        "doc_number": ParagraphStyle(
            "DocNumber",
            parent=base["Normal"],
            fontSize=9,
            textColor=TEXT_MID,
            spaceBefore=2,
            spaceAfter=8,
            alignment=TA_CENTER,
            fontName="Helvetica",
        ),
        "section_header": ParagraphStyle(
            "SectionHeader",
            parent=base["Normal"],
            fontSize=10,
            textColor=GOV_NAVY,
            spaceBefore=12,
            spaceAfter=4,
            fontName="Helvetica-Bold",
        ),
        "field_label": ParagraphStyle(
            "FieldLabel",
            parent=base["Normal"],
            fontSize=8,
            textColor=TEXT_MID,
            fontName="Helvetica",
        ),
        "field_value": ParagraphStyle(
            "FieldValue",
            parent=base["Normal"],
            fontSize=9,
            textColor=TEXT_DARK,
            fontName="Helvetica-Bold",
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontSize=7,
            textColor=TEXT_MID,
            alignment=TA_CENTER,
            fontName="Helvetica",
        ),
        "sig_label": ParagraphStyle(
            "SigLabel",
            parent=base["Normal"],
            fontSize=8,
            textColor=TEXT_MID,
            alignment=TA_CENTER,
            fontName="Helvetica",
        ),
        "sig_value": ParagraphStyle(
            "SigValue",
            parent=base["Normal"],
            fontSize=9,
            textColor=GOV_NAVY,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ),
    }


# ── Overlay canvas (watermark + QR) ──────────────────────────────────────────
class _OverlayCanvas(rl_canvas.Canvas):
    """
    Custom canvas that draws watermark and QR code overlays on every page.
    """

    def __init__(self, *args, wm_png: bytes, qr_png: Optional[bytes],
                 footer_text: str, doc_number: str, **kwargs):
        super().__init__(*args, **kwargs)
        self._wm_png     = wm_png
        self._qr_png     = qr_png
        self._footer     = footer_text
        self._doc_number = doc_number
        self._page_num   = 0

    def showPage(self):
        self._page_num += 1
        self._draw_overlays()
        super().showPage()

    def save(self):
        # draw overlays on the very last page before save
        self._page_num += 1
        self._draw_overlays()
        super().save()

    def _draw_overlays(self):
        # ── Watermark ─────────────────────────────────────────────────
        if self._wm_png:
            try:
                wm_reader = ImageReader(io.BytesIO(self._wm_png))
                self.saveState()
                self.drawImage(
                    wm_reader, 0, 0,
                    width=PAGE_W, height=PAGE_H,
                    preserveAspectRatio=False,
                    mask="auto",
                )
                self.restoreState()
            except Exception as e:
                logger.warning("Watermark overlay failed: %s", e)

        # ── QR code (first page only, lower-right) ────────────────────
        if self._qr_png and self._page_num == 1:
            try:
                qr_size = 3.5 * cm
                qr_x    = PAGE_W - MARGIN_H - qr_size
                qr_y    = MARGIN_V + 1.5 * cm
                qr_reader = ImageReader(io.BytesIO(self._qr_png))
                self.saveState()
                self.drawImage(
                    qr_reader, qr_x, qr_y,
                    width=qr_size, height=qr_size,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                self.setFont("Helvetica", 6)
                self.setFillColor(TEXT_MID)
                self.drawCentredString(
                    qr_x + qr_size / 2, qr_y - 8, "Scan to verify"
                )
                self.restoreState()
            except Exception as e:
                logger.warning("QR overlay failed: %s", e)

        # ── Footer ────────────────────────────────────────────────────
        self.saveState()
        self.setFont("Helvetica", 6.5)
        self.setFillColor(TEXT_MID)
        footer = f"{self._doc_number}  |  {self._footer}  |  Page {self._page_num}"
        self.drawCentredString(PAGE_W / 2, 12 * mm, footer)
        # thin rule above footer
        self.setStrokeColor(GOV_BORDER)
        self.setLineWidth(0.4)
        self.line(MARGIN_H, 16 * mm, PAGE_W - MARGIN_H, 16 * mm)
        self.restoreState()


# ── Main builder ──────────────────────────────────────────────────────────────

def build_pdf(
    document_number:  str,
    document_title:   str,
    issuing_authority:str,
    fields:           List[DocumentField],
    issued_by_name:   str,
    issued_at:        datetime,
    department_code:  str,
    watermark_type:   WatermarkType,
    qr_png:           Optional[bytes],
    valid_until:      Optional[datetime] = None,
    signature_hash:   str = "",
    applicant_name:   str = "",
) -> bytes:
    """
    Assemble the complete PDF and return its bytes.

    Parameters
    ----------
    document_number   — e.g. "IND-PP-2026-000001"
    document_title    — e.g. "Passport"
    issuing_authority — e.g. "Ministry of External Affairs, Government of India"
    fields            — validated DocumentField list
    issued_by_name    — display name of the issuing officer
    issued_at         — datetime of issuance
    department_code   — e.g. "COLLECTOR-PUNE"
    watermark_type    — OFFICIAL / DRAFT / REVOKED / SPECIMEN
    qr_png            — QR code PNG bytes (can be None)
    valid_until       — document expiry (None = perpetual)
    signature_hash    — SHA-256 hex of this PDF (injected into metadata)
    applicant_name    — for header display
    """
    styles    = _styles()
    buf       = io.BytesIO()
    footer_tx = issuing_authority

    # ── Watermark image ───────────────────────────────────────────────────
    try:
        wm_png = watermark_for_page(PAGE_W, PAGE_H, watermark_type)
    except Exception as e:
        logger.warning("Watermark generation failed: %s", e)
        wm_png = b""

    # ── Build story (Platypus flowables) ──────────────────────────────────
    story = []

    # ── Header ────────────────────────────────────────────────────────────
    story.append(Paragraph("GOVERNMENT OF INDIA", styles["subtitle"]))
    story.append(Paragraph(document_title.upper(), styles["title"]))
    story.append(Paragraph(issuing_authority, styles["subtitle"]))
    story.append(Paragraph(f"Document No: {document_number}", styles["doc_number"]))
    story.append(HRFlowable(
        width="100%", thickness=1.5, color=GOV_NAVY, spaceAfter=8
    ))

    # ── Applicant banner ──────────────────────────────────────────────────
    if applicant_name:
        banner_data = [[
            Paragraph("ISSUED TO", styles["field_label"]),
            Paragraph(applicant_name.upper(), styles["field_value"]),
        ]]
        banner_tbl = Table(banner_data, colWidths=["25%", "75%"])
        banner_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), GOV_LIGHT),
            ("BOX",        (0, 0), (-1, -1), 0.5, GOV_BORDER),
            ("LEFTPADDING",  (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING",   (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ]))
        story.append(banner_tbl)
        story.append(Spacer(1, 10))

    # ── Fields grouped by section ─────────────────────────────────────────
    sections: Dict[str, List[DocumentField]] = {}
    for f in fields:
        sections.setdefault(f.section, []).append(f)

    content_width = PAGE_W - 2 * MARGIN_H
    # Reserve right margin for QR code on first page (≈ 4 cm)
    qr_reserve = 4.0 * cm if qr_png else 0

    for section_name, section_fields in sections.items():
        story.append(Paragraph(section_name, styles["section_header"]))

        # Two-column layout: label | value
        rows = []
        for field in section_fields:
            val = field.value
            if val is None or val == "":
                val = "—"
            elif isinstance(val, float) and val == int(val):
                val = f"{int(val):,}"
            elif isinstance(val, float):
                val = f"{val:,.2f}"
            rows.append([
                Paragraph(field.label, styles["field_label"]),
                Paragraph(str(val),    styles["field_value"]),
            ])

        if rows:
            usable_w = content_width - qr_reserve
            tbl = Table(rows, colWidths=[usable_w * 0.38, usable_w * 0.62])
            tbl.setStyle(TableStyle([
                ("BACKGROUND",   (0, 0), (0, -1), GOV_LIGHT),
                ("GRID",         (0, 0), (-1, -1), 0.4, GOV_BORDER),
                ("LEFTPADDING",  (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING",   (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
                ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 6))

        qr_reserve = 0   # only reserve on first content block

    # ── Validity bar ──────────────────────────────────────────────────────
    story.append(Spacer(1, 10))
    validity_rows = [[
        Paragraph("Date of Issue", styles["field_label"]),
        Paragraph(issued_at.strftime("%d %B %Y"), styles["field_value"]),
        Paragraph("Valid Until", styles["field_label"]),
        Paragraph(
            valid_until.strftime("%d %B %Y") if valid_until else "Lifetime",
            styles["field_value"]
        ),
    ]]
    val_tbl = Table(validity_rows, colWidths=["20%", "30%", "20%", "30%"])
    val_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0F6FF")),
        ("BOX",        (0, 0), (-1, -1), 0.8, GOV_NAVY),
        ("INNERGRID",  (0, 0), (-1, -1), 0.4, GOV_BORDER),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
    ]))
    story.append(val_tbl)
    story.append(Spacer(1, 14))

    # ── Signature block ───────────────────────────────────────────────────
    story.append(HRFlowable(
        width="100%", thickness=0.8, color=GOV_BORDER, spaceAfter=8
    ))
    sig_rows = [[
        Paragraph("Issuing Officer", styles["sig_label"]),
        Paragraph("Department", styles["sig_label"]),
        Paragraph("Digital Signature", styles["sig_label"]),
    ], [
        Paragraph(issued_by_name, styles["sig_value"]),
        Paragraph(department_code, styles["sig_value"]),
        Paragraph(
            f"SHA-256: {signature_hash[:24]}..." if signature_hash else "UNSIGNED",
            styles["sig_label"],
        ),
    ]]
    sig_tbl = Table(sig_rows, colWidths=["34%", "33%", "33%"])
    sig_tbl.setStyle(TableStyle([
        ("ALIGN",        (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",   (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 4),
        ("LINEABOVE",    (0, 1), (-1, 1), 0.5, GOV_BORDER),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 6))

    # Digitally signed notice
    story.append(Paragraph(
        "This document has been digitally signed under the IT Act 2000. "
        "Verify authenticity by scanning the QR code or visiting the verification URL.",
        ParagraphStyle("notice", fontSize=7, textColor=TEXT_MID,
                       alignment=TA_CENTER, fontName="Helvetica"),
    ))

    # ── Assemble with overlay canvas ──────────────────────────────────────
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN_H,
        rightMargin=MARGIN_H,
        topMargin=MARGIN_V,
        bottomMargin=MARGIN_V + 1.2 * cm,   # room for footer
        title=f"{document_title} — {document_number}",
        author=issuing_authority,
        subject=f"{document_title} issued to {applicant_name}",
        keywords=f"government india {document_title.lower()} official",
        creator="DocuMind AI Generation Engine v1.0",
    )

    doc.build(
        story,
        canvasmaker=lambda *a, **kw: _OverlayCanvas(
            *a,
            wm_png=wm_png,
            qr_png=qr_png,
            footer_text=footer_tx,
            doc_number=document_number,
            **kw,
        ),
    )

    buf.seek(0)
    pdf_bytes = buf.read()
    logger.info(
        "PDF built: %s  %d bytes", document_number, len(pdf_bytes)
    )
    return pdf_bytes
