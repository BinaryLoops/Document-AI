"""
ai_engine/extractors.py -- Core extraction utilities used across all AI modules.

Extracts structured data from government document text:
  - Dates & deadlines
  - Monetary amounts
  - Organizations / departments
  - People names
  - Locations
  - Case numbers & references
  - Key points / sentences

All extractors return results with confidence scores and evidence.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Evidence wrapper ─────────────────────────────────────────────────────────

@dataclass
class ExtractedItem:
    """A single extracted item with evidence."""
    value: str
    category: str             # e.g. "date", "person", "amount"
    confidence: float = 0.0   # 0.0-1.0
    evidence: str = ""        # verbatim snippet where it was found
    source: str = ""          # document name / chunk ID
    position: int = -1        # char offset in text

    def to_dict(self) -> Dict[str, Any]:
        return {
            "value": self.value,
            "category": self.category,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence[:200],
            "source": self.source,
        }


# ── Date & Deadline Extraction ───────────────────────────────────────────────

# Common date patterns
_DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY
    (r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4})\b', 0.9),
    # DD/MM/YY
    (r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2})\b', 0.7),
    # Month DD, YYYY
    (r'\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b', 0.95),
    # DD Month YYYY
    (r'\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b', 0.95),
    # YYYY-MM-DD (ISO)
    (r'\b(\d{4}-\d{2}-\d{2})\b', 0.95),
]

_DEADLINE_KEYWORDS = [
    "deadline", "due date", "last date", "expiry", "expires",
    "valid until", "valid till", "valid up to", "before",
    "not later than", "on or before", "by", "within",
]


def extract_dates(text: str, source: str = "") -> List[ExtractedItem]:
    """Extract all dates from text."""
    results = []
    seen = set()

    for pattern, base_conf in _DATE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            val = match.group(1).strip()
            if val in seen:
                continue
            seen.add(val)

            # Get surrounding context
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            context = text[start:end].strip()

            # Check if it's a deadline
            pre_text = text[max(0, match.start() - 80):match.start()].lower()
            is_deadline = any(kw in pre_text for kw in _DEADLINE_KEYWORDS)

            results.append(ExtractedItem(
                value=val,
                category="deadline" if is_deadline else "date",
                confidence=base_conf + (0.05 if is_deadline else 0),
                evidence=context,
                source=source,
                position=match.start(),
            ))

    return results


# ── Amount Extraction ────────────────────────────────────────────────────────

_AMOUNT_PATTERNS = [
    (r'(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{1,2})?)\s*(?:/-|lakh|crore|thousand)?', 0.9),
    (r'([\d,]+(?:\.\d{1,2})?)\s*(?:rupees|/-)', 0.85),
    (r'(?:amount|sum|total|fee|fine|penalty|cost)\s*(?:of|:)?\s*(?:Rs\.?|INR|₹)?\s*([\d,]+(?:\.\d{1,2})?)', 0.85),
]


def extract_amounts(text: str, source: str = "") -> List[ExtractedItem]:
    """Extract monetary amounts from text."""
    results = []
    seen = set()

    for pattern, base_conf in _AMOUNT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            val = match.group(1).strip().replace(",", "")
            if val in seen or not val:
                continue
            try:
                float(val)
            except ValueError:
                continue
            seen.add(val)

            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 40)
            context = text[start:end].strip()

            results.append(ExtractedItem(
                value=f"Rs. {val}",
                category="amount",
                confidence=base_conf,
                evidence=context,
                source=source,
                position=match.start(),
            ))

    return results


# ── Case Number Extraction ───────────────────────────────────────────────────

_CASE_PATTERNS = [
    # FIR numbers
    (r'\bFIR\s*(?:No\.?|Number)?\s*[:\-]?\s*(\d{1,6}/\d{2,4})', "fir_number", 0.95),
    # Writ Petition / Civil Suit etc.
    (r'\b((?:W\.?P\.?|C\.?A\.?|S\.?L\.?P\.?|Crl\.?\s*A\.?|Civil\s*Suit|Criminal\s*Case)\s*(?:\(C\)|\(Crl\))?\s*No\.?\s*\d{1,8}(?:/\d{2,4})?)', "case_number", 0.90),
    # Generic case number
    (r'\b(?:Case|Complaint|Appeal)\s*(?:No\.?|Number)\s*[:\-]?\s*([A-Z0-9/\-]{4,20})', "case_number", 0.85),
    # Reference numbers
    (r'\b(?:Ref|Reference)\s*(?:No\.?|Number)\s*[:\-]?\s*([A-Z0-9/\-]{4,20})', "reference_number", 0.80),
]


def extract_case_numbers(text: str, source: str = "") -> List[ExtractedItem]:
    """Extract case numbers, FIR numbers, and reference numbers."""
    results = []
    seen = set()

    for pattern, category, base_conf in _CASE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            val = match.group(1).strip() if match.lastindex else match.group(0).strip()
            if val in seen:
                continue
            seen.add(val)

            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 40)

            results.append(ExtractedItem(
                value=val,
                category=category,
                confidence=base_conf,
                evidence=text[start:end].strip(),
                source=source,
                position=match.start(),
            ))

    return results


# ── Person Name Extraction ───────────────────────────────────────────────────

_PERSON_LABELS = [
    "name", "applicant", "petitioner", "respondent", "complainant",
    "accused", "plaintiff", "defendant", "father", "mother",
    "husband", "wife", "son", "daughter", "witness",
    "judge", "magistrate", "officer", "inspector", "collector",
    "commissioner", "registrar", "superintendent",
]


def extract_people(text: str, source: str = "") -> List[ExtractedItem]:
    """Extract person names from text using label patterns and NER fallback."""
    results = []
    seen = set()

    # Pattern: Label: Name
    for label in _PERSON_LABELS:
        pattern = rf'(?:{label})\s*[:\-]\s*([A-Z][a-zA-Z\.\s]{{2,40}}?)(?:\s*[,\n\r]|\s+(?:S/o|D/o|W/o|son|daughter|age|aged|resident))'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            name = match.group(1).strip().rstrip(".,;:")
            if name in seen or len(name) < 3:
                continue
            seen.add(name)

            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)

            results.append(ExtractedItem(
                value=name,
                category="person",
                confidence=0.80,
                evidence=text[start:end].strip(),
                source=source,
                position=match.start(),
            ))

    # Fallback: S/o, D/o, W/o patterns
    sdo_pattern = r'([A-Z][a-zA-Z\.\s]{2,30}?)\s+(?:S/o|D/o|W/o|son of|daughter of|wife of)\s+([A-Z][a-zA-Z\.\s]{2,30})'
    for match in re.finditer(sdo_pattern, text):
        for i in [1, 2]:
            name = match.group(i).strip().rstrip(".,;:")
            if name not in seen and len(name) >= 3:
                seen.add(name)
                results.append(ExtractedItem(
                    value=name,
                    category="person",
                    confidence=0.75,
                    evidence=match.group(0)[:100],
                    source=source,
                    position=match.start(),
                ))

    return results


# ── Organization / Department Extraction ─────────────────────────────────────

_ORG_PATTERNS = [
    (r'\b((?:Ministry|Department|Directorate|Bureau|Commission|Authority|Board|Council|Office|Secretariat|Division)\s+(?:of\s+)?[A-Z][a-zA-Z\s&,]{3,50})', 0.85),
    (r'\b((?:District|State|Central|National|Regional)\s+(?:Court|Tribunal|Commission|Authority|Board|Office)[A-Za-z\s,]{0,30})', 0.80),
    (r'\b((?:High Court|Supreme Court|District Court|Sessions Court|Magistrate Court|Tribunal)\s*(?:of\s+)?[A-Za-z\s]{0,30})', 0.90),
    (r'\b((?:Police Station|Thana)\s+[A-Za-z\s]{2,30})', 0.85),
    (r'\b((?:Municipal\s+Corporation|Nagar\s+Palika|Gram\s+Panchayat|Zilla\s+Parishad)\s*(?:of\s+)?[A-Za-z\s]{0,30})', 0.85),
    (r'\b([A-Z][a-zA-Z\s]{2,30}(?:University|Institute|College|School|Academy))', 0.80),
]


def extract_organizations(text: str, source: str = "") -> List[ExtractedItem]:
    """Extract organizations, departments, courts, and institutions."""
    results = []
    seen = set()

    for pattern, base_conf in _ORG_PATTERNS:
        for match in re.finditer(pattern, text):
            val = match.group(1).strip().rstrip(".,;:")
            val_lower = val.lower()
            if val_lower in seen or len(val) < 5:
                continue
            seen.add(val_lower)

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)

            results.append(ExtractedItem(
                value=val,
                category="organization",
                confidence=base_conf,
                evidence=text[start:end].strip(),
                source=source,
                position=match.start(),
            ))

    return results


# ── Location Extraction ──────────────────────────────────────────────────────

_LOCATION_LABELS = [
    "address", "place", "village", "town", "city", "district",
    "state", "taluka", "tehsil", "block", "ward", "locality",
    "place of birth", "place of issue", "place of occurrence",
    "residence", "resident of",
]


def extract_locations(text: str, source: str = "") -> List[ExtractedItem]:
    """Extract locations from text."""
    results = []
    seen = set()

    for label in _LOCATION_LABELS:
        pattern = rf'(?:{label})\s*[:\-]\s*([A-Za-z][A-Za-z\s,\.\-]{{2,60}}?)(?:\s*[;\n\r]|,\s*(?:Pin|PIN|Dist|State|Ph))'
        for match in re.finditer(pattern, text, re.IGNORECASE):
            val = match.group(1).strip().rstrip(".,;:")
            if val.lower() in seen or len(val) < 3:
                continue
            seen.add(val.lower())

            start = max(0, match.start() - 20)
            end = min(len(text), match.end() + 20)

            results.append(ExtractedItem(
                value=val,
                category="location",
                confidence=0.75,
                evidence=text[start:end].strip(),
                source=source,
                position=match.start(),
            ))

    # PIN code pattern
    pin_pattern = r'\b(\d{6})\b'
    for match in re.finditer(pin_pattern, text):
        pre = text[max(0, match.start() - 40):match.start()].lower()
        if any(kw in pre for kw in ["pin", "zip", "postal", "code"]):
            val = match.group(1)
            if val not in seen:
                seen.add(val)
                results.append(ExtractedItem(
                    value=f"PIN {val}",
                    category="location",
                    confidence=0.70,
                    evidence=text[max(0, match.start()-30):match.end()+10].strip(),
                    source=source,
                    position=match.start(),
                ))

    return results


# ── Key Sentence Extraction ─────────────────────────────────────────────────

_KEY_INDICATORS = [
    "hereby", "ordered", "directed", "granted", "rejected",
    "approved", "certified", "verified", "declared", "notified",
    "whereas", "therefore", "accordingly", "in view of",
    "subject to", "provided that", "it is mandatory",
    "penalty", "fine", "imprisonment", "punishment",
    "valid", "effective", "applicable", "binding",
]


def extract_key_points(text: str, source: str = "", max_points: int = 10) -> List[ExtractedItem]:
    """Extract key sentences / points from text."""
    results = []

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    scored: List[Tuple[float, str, int]] = []
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if len(sent) < 20 or len(sent) > 300:
            continue

        score = 0.0
        sent_lower = sent.lower()

        # Keyword scoring
        for kw in _KEY_INDICATORS:
            if kw in sent_lower:
                score += 0.15

        # Contains a date
        if re.search(r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}', sent):
            score += 0.1

        # Contains an amount
        if re.search(r'(?:Rs\.?|₹|INR)\s*[\d,]+', sent):
            score += 0.1

        # Contains a person reference
        if re.search(r'(?:Mr\.|Mrs\.|Ms\.|Shri|Smt|Dr\.)', sent):
            score += 0.05

        # Position bias (first and last sentences are often important)
        if i < 3 or i >= len(sentences) - 2:
            score += 0.1

        score = min(score, 1.0)
        if score >= 0.15:
            scored.append((score, sent, i))

    # Sort by score, take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    for score, sent, pos in scored[:max_points]:
        results.append(ExtractedItem(
            value=sent,
            category="key_point",
            confidence=score,
            evidence=sent,
            source=source,
            position=pos,
        ))

    return results


# ── Convenience: extract everything ──────────────────────────────────────────

def extract_all(text: str, source: str = "") -> Dict[str, List[ExtractedItem]]:
    """Run all extractors and return categorized results."""
    return {
        "dates": extract_dates(text, source),
        "amounts": extract_amounts(text, source),
        "case_numbers": extract_case_numbers(text, source),
        "people": extract_people(text, source),
        "organizations": extract_organizations(text, source),
        "locations": extract_locations(text, source),
        "key_points": extract_key_points(text, source),
    }
