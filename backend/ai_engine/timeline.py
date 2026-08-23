"""
ai_engine/timeline.py -- Timeline Extraction module.

Generates chronological events from government documents.
Each event includes:
  - date (parsed)
  - description (what happened)
  - event_type (filing, issuance, hearing, deadline, etc.)
  - confidence & evidence
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ai_engine.extractors import extract_dates, ExtractedItem

logger = logging.getLogger(__name__)


class EventType:
    FILING = "filing"
    ISSUANCE = "issuance"
    HEARING = "hearing"
    DEADLINE = "deadline"
    BIRTH = "birth"
    EXPIRY = "expiry"
    ORDER = "order"
    OCCURRENCE = "occurrence"
    REGISTRATION = "registration"
    AMENDMENT = "amendment"
    OTHER = "other"


# Map keywords to event types
_EVENT_KEYWORD_MAP = {
    EventType.FILING: ["filed", "filing", "submitted", "lodged", "registered complaint"],
    EventType.ISSUANCE: ["issued", "granted", "sanctioned", "approved", "certified"],
    EventType.HEARING: ["hearing", "next date", "adjourned", "listed", "posted"],
    EventType.DEADLINE: ["deadline", "last date", "due date", "expiry", "expires", "valid until", "valid till"],
    EventType.BIRTH: ["born", "date of birth", "dob"],
    EventType.EXPIRY: ["expired", "lapsed", "expiry", "expires on"],
    EventType.ORDER: ["ordered", "directed", "decreed", "judgment", "verdict"],
    EventType.OCCURRENCE: ["occurred", "happened", "incident", "occurrence", "took place"],
    EventType.REGISTRATION: ["registered", "registration", "enrolled"],
    EventType.AMENDMENT: ["amended", "modified", "revised", "updated"],
}


@dataclass
class TimelineEvent:
    """A single event in the timeline."""
    date_str: str = ""
    date_parsed: Optional[str] = None   # ISO format if parseable
    description: str = ""
    event_type: str = EventType.OTHER
    confidence: float = 0.0
    evidence: str = ""
    source: str = ""
    sort_key: str = ""   # for chronological sorting

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date_str,
            "date_iso": self.date_parsed,
            "description": self.description,
            "event_type": self.event_type,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence[:200],
            "source": self.source,
        }


class TimelineExtractor:
    """
    Extract chronological events from government documents.

    Usage::

        extractor = TimelineExtractor()
        events = extractor.extract(text)
    """

    def extract(
        self,
        text: str,
        source: str = "",
        document_type: str = "",
    ) -> List[TimelineEvent]:
        """
        Extract timeline events from text.

        Returns events sorted chronologically.
        """
        events = []
        seen_dates: set = set()

        # Extract all dates first
        date_items = extract_dates(text, source)

        for date_item in date_items:
            if date_item.value in seen_dates:
                continue
            seen_dates.add(date_item.value)

            # Get surrounding context (120 chars each side)
            pos = date_item.position
            ctx_start = max(0, pos - 120)
            ctx_end = min(len(text), pos + len(date_item.value) + 120)
            context = text[ctx_start:ctx_end].strip()

            # Determine event type from context
            event_type = self._classify_event(context)

            # Build description
            description = self._build_description(context, date_item.value, event_type)

            # Try to parse date for sorting
            parsed = self._parse_date(date_item.value)

            events.append(TimelineEvent(
                date_str=date_item.value,
                date_parsed=parsed,
                description=description,
                event_type=event_type,
                confidence=date_item.confidence,
                evidence=context,
                source=source,
                sort_key=parsed or date_item.value,
            ))

        # Also extract sentence-level events
        sentence_events = self._extract_sentence_events(text, source, seen_dates)
        events.extend(sentence_events)

        # Sort chronologically
        events.sort(key=lambda e: e.sort_key)

        logger.info("Extracted %d timeline events from document", len(events))
        return events

    def _classify_event(self, context: str) -> str:
        """Classify event type from surrounding context."""
        ctx_lower = context.lower()
        for event_type, keywords in _EVENT_KEYWORD_MAP.items():
            if any(kw in ctx_lower for kw in keywords):
                return event_type
        return EventType.OTHER

    def _build_description(self, context: str, date_str: str, event_type: str) -> str:
        """Build a human-readable event description."""
        # Extract the sentence containing the date
        sentences = re.split(r'[.!?]\s+', context)
        for sent in sentences:
            if date_str in sent:
                desc = sent.strip()
                if len(desc) > 15:
                    return desc

        # Fallback: use the event type
        type_label = event_type.replace("_", " ").title()
        return f"{type_label} on {date_str}"

    def _parse_date(self, date_str: str) -> Optional[str]:
        """Try to parse a date string into ISO format."""
        formats = [
            "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y",
            "%d/%m/%y", "%d-%m-%y",
            "%Y-%m-%d",
            "%B %d, %Y", "%B %d %Y",
            "%d %B %Y", "%d %b %Y",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _extract_sentence_events(
        self, text: str, source: str, seen_dates: set
    ) -> List[TimelineEvent]:
        """Extract events from sentences that describe temporal actions."""
        events = []
        # Look for temporal action patterns without explicit dates
        patterns = [
            (r'(?:on|dated)\s+(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\s*[,;]?\s*(.{10,80})', 0.75),
            (r'(.{10,60})\s+(?:on|dated)\s+(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})', 0.75),
        ]

        for pattern, conf in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                groups = match.groups()
                # Determine which group is date vs description
                date_str = None
                desc = None
                for g in groups:
                    if re.match(r'\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}', g.strip()):
                        date_str = g.strip()
                    else:
                        desc = g.strip()

                if date_str and date_str not in seen_dates and desc:
                    seen_dates.add(date_str)
                    parsed = self._parse_date(date_str)
                    events.append(TimelineEvent(
                        date_str=date_str,
                        date_parsed=parsed,
                        description=desc.rstrip(".,;:"),
                        event_type=self._classify_event(desc),
                        confidence=conf,
                        evidence=match.group(0)[:200],
                        source=source,
                        sort_key=parsed or date_str,
                    ))

        return events
