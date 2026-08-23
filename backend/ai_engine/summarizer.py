"""
ai_engine/summarizer.py -- Government Document Summarization.

Extracts:
  - key points
  - important dates & deadlines
  - organizations & departments
  - people (citizens, officers)
  - locations
  - amounts
  - case numbers

Every extracted item includes evidence (verbatim snippet).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ai_engine.extractors import (
    ExtractedItem,
    extract_all,
    extract_amounts,
    extract_case_numbers,
    extract_dates,
    extract_key_points,
    extract_locations,
    extract_organizations,
    extract_people,
)

logger = logging.getLogger(__name__)


@dataclass
class DocumentSummary:
    """Comprehensive summary of a government document."""
    document_id: str = ""
    document_type: str = ""
    source: str = ""

    # Core summary
    summary_text: str = ""
    key_points: List[Dict[str, Any]] = field(default_factory=list)

    # Extracted entities
    dates: List[Dict[str, Any]] = field(default_factory=list)
    deadlines: List[Dict[str, Any]] = field(default_factory=list)
    amounts: List[Dict[str, Any]] = field(default_factory=list)
    case_numbers: List[Dict[str, Any]] = field(default_factory=list)
    people: List[Dict[str, Any]] = field(default_factory=list)
    organizations: List[Dict[str, Any]] = field(default_factory=list)
    locations: List[Dict[str, Any]] = field(default_factory=list)

    # Metadata
    word_count: int = 0
    confidence: float = 0.0
    extraction_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "document_type": self.document_type,
            "source": self.source,
            "summary_text": self.summary_text,
            "key_points": self.key_points,
            "dates": self.dates,
            "deadlines": self.deadlines,
            "amounts": self.amounts,
            "case_numbers": self.case_numbers,
            "people": self.people,
            "organizations": self.organizations,
            "locations": self.locations,
            "word_count": self.word_count,
            "confidence": round(self.confidence, 3),
            "extraction_count": self.extraction_count,
        }


class DocumentSummarizer:
    """
    Generates comprehensive summaries of government documents.

    Usage::

        summarizer = DocumentSummarizer()
        summary = summarizer.summarize(text, document_id="abc", document_type="fir")
    """

    def summarize(
        self,
        text: str,
        document_id: str = "",
        document_type: str = "",
        source: str = "",
        max_key_points: int = 10,
    ) -> DocumentSummary:
        """
        Generate a full summary with extracted entities.

        Args:
            text: Document text (from OCR or direct extraction).
            document_id: ID of the document in the locker.
            document_type: Category (passport, fir, etc.).
            source: Source filename.
            max_key_points: Maximum key points to extract.

        Returns:
            DocumentSummary with all extracted items and evidence.
        """
        summary = DocumentSummary(
            document_id=document_id,
            document_type=document_type,
            source=source,
            word_count=len(text.split()),
        )

        # Run all extractors
        all_items = extract_all(text, source=source)

        # Key points
        kps = extract_key_points(text, source, max_points=max_key_points)
        summary.key_points = [item.to_dict() for item in kps]

        # Dates and deadlines
        dates_items = all_items["dates"]
        summary.dates = [
            item.to_dict() for item in dates_items if item.category == "date"
        ]
        summary.deadlines = [
            item.to_dict() for item in dates_items if item.category == "deadline"
        ]

        # Amounts
        summary.amounts = [item.to_dict() for item in all_items["amounts"]]

        # Case numbers
        summary.case_numbers = [item.to_dict() for item in all_items["case_numbers"]]

        # People
        summary.people = [item.to_dict() for item in all_items["people"]]

        # Organizations
        summary.organizations = [item.to_dict() for item in all_items["organizations"]]

        # Locations
        summary.locations = [item.to_dict() for item in all_items["locations"]]

        # Generate summary text
        summary.summary_text = self._build_summary_text(summary)

        # Overall confidence
        all_confs = [item.confidence for items in all_items.values() for item in items]
        summary.confidence = sum(all_confs) / len(all_confs) if all_confs else 0.0
        summary.extraction_count = len(all_confs)

        logger.info(
            "Summarized document %s: %d key points, %d dates, %d people, "
            "%d orgs, %d amounts, %d cases",
            document_id, len(summary.key_points), len(summary.dates),
            len(summary.people), len(summary.organizations),
            len(summary.amounts), len(summary.case_numbers),
        )

        return summary

    def _build_summary_text(self, summary: DocumentSummary) -> str:
        """Build a natural-language summary from extracted data."""
        parts = []

        # Document type intro
        if summary.document_type:
            dtype = summary.document_type.replace("_", " ").title()
            parts.append(f"This is a {dtype} document.")

        # Key points
        if summary.key_points:
            parts.append(f"Key findings ({len(summary.key_points)}):")
            for i, kp in enumerate(summary.key_points[:5], 1):
                parts.append(f"  {i}. {kp['value']}")

        # People
        if summary.people:
            names = [p["value"] for p in summary.people[:5]]
            parts.append(f"People mentioned: {', '.join(names)}.")

        # Organizations
        if summary.organizations:
            orgs = [o["value"] for o in summary.organizations[:5]]
            parts.append(f"Organizations: {', '.join(orgs)}.")

        # Dates
        if summary.dates:
            dates = [d["value"] for d in summary.dates[:5]]
            parts.append(f"Important dates: {', '.join(dates)}.")

        # Deadlines
        if summary.deadlines:
            dls = [d["value"] for d in summary.deadlines[:3]]
            parts.append(f"Deadlines: {', '.join(dls)}.")

        # Amounts
        if summary.amounts:
            amts = [a["value"] for a in summary.amounts[:3]]
            parts.append(f"Amounts: {', '.join(amts)}.")

        # Cases
        if summary.case_numbers:
            cases = [c["value"] for c in summary.case_numbers[:3]]
            parts.append(f"Case references: {', '.join(cases)}.")

        # Locations
        if summary.locations:
            locs = [l["value"] for l in summary.locations[:3]]
            parts.append(f"Locations: {', '.join(locs)}.")

        return "\n".join(parts) if parts else "No significant content could be extracted."
