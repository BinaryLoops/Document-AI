"""
ai_engine/assistant.py -- Evidence-backed AI Assistant.

Answers questions about documents with evidence:
  - What is this document about?
  - Which department issued it?
  - Is it verified?
  - What is the deadline?
  - Is there an ongoing case?

Every answer includes:
  - answer text
  - confidence
  - evidence (source snippets)
  - reasoning (why this answer)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ai_engine.extractors import (
    extract_all,
    extract_case_numbers,
    extract_dates,
    extract_organizations,
)

logger = logging.getLogger(__name__)


@dataclass
class AssistantAnswer:
    """An evidence-backed answer from the AI assistant."""
    question: str = ""
    answer: str = ""
    confidence: float = 0.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    reasoning: str = ""
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence[:10],
            "reasoning": self.reasoning,
            "sources": self.sources,
        }


# ── Question intent classification ──────────────────────────────────────────

class QuestionIntent:
    ABOUT = "about"               # What is this document about?
    DEPARTMENT = "department"     # Which department issued it?
    VERIFIED = "verified"        # Is it verified?
    DEADLINE = "deadline"        # What is the deadline?
    ONGOING_CASE = "ongoing_case"  # Is there an ongoing case?
    PERSON = "person"            # Who is mentioned?
    DATE = "date"                # What are the important dates?
    AMOUNT = "amount"            # What is the amount?
    LOCATION = "location"        # Where was it issued?
    GENERAL = "general"          # General question


_INTENT_PATTERNS = {
    QuestionIntent.ABOUT: [
        r"what\s+(?:is|does)\s+this\s+document\s+(?:about|contain|say)",
        r"summary|summarize|summarise|overview|describe",
        r"what\s+(?:is|are)\s+the\s+(?:content|subject|topic)",
    ],
    QuestionIntent.DEPARTMENT: [
        r"which\s+department|issued\s+by|issuing\s+(?:authority|body|office)",
        r"who\s+issued|department|authority|ministry|office",
    ],
    QuestionIntent.VERIFIED: [
        r"is\s+(?:it|this|the\s+document)\s+verified",
        r"verification\s+status|trust\s+(?:badge|level|score)",
        r"authentic|genuine|valid|legitimate",
    ],
    QuestionIntent.DEADLINE: [
        r"deadline|due\s+date|last\s+date|expir",
        r"when\s+(?:does|will)\s+(?:it|this)\s+expire",
        r"valid\s+(?:until|till|upto)",
    ],
    QuestionIntent.ONGOING_CASE: [
        r"ongoing\s+case|active\s+case|pending\s+case",
        r"is\s+there\s+(?:a|an|any)\s+(?:ongoing|active|pending)\s+case",
        r"case\s+status|fir|complaint",
    ],
    QuestionIntent.PERSON: [
        r"who\s+(?:is|are)|person|people|name|citizen|officer",
        r"applicant|petitioner|respondent|accused|complainant",
    ],
    QuestionIntent.DATE: [
        r"(?:what|when)\s+(?:is|are)\s+the\s+(?:important|key)?\s*date",
        r"date\s+of\s+(?:issue|birth|filing|hearing)",
    ],
    QuestionIntent.AMOUNT: [
        r"(?:what|how\s+much)\s+(?:is|are)\s+the\s+(?:amount|fee|fine|cost)",
        r"(?:Rs|rupee|INR|amount|sum|total|fee|fine|penalty)",
    ],
    QuestionIntent.LOCATION: [
        r"where|location|address|place|district|state|city",
        r"jurisdiction|area|region",
    ],
}


class AIAssistant:
    """
    Evidence-backed AI assistant for government document Q&A.

    Every answer includes evidence (verbatim source text) and reasoning.
    """

    def ask(
        self,
        question: str,
        text: str,
        document_id: str = "",
        document_type: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        verification_status: str = "",
    ) -> AssistantAnswer:
        """
        Answer a question about a document with evidence.

        Args:
            question: User's question.
            text: Document text (OCR or extracted).
            document_id: Document ID.
            document_type: Document category.
            metadata: Document metadata dict.
            verification_status: Current verification status.

        Returns:
            AssistantAnswer with evidence and reasoning.
        """
        meta = metadata or {}
        intent = self._classify_intent(question)

        logger.info(
            "Assistant question='%s' intent=%s doc=%s",
            question[:60], intent, document_id,
        )

        # Route to specific handler
        handlers = {
            QuestionIntent.ABOUT: self._answer_about,
            QuestionIntent.DEPARTMENT: self._answer_department,
            QuestionIntent.VERIFIED: self._answer_verified,
            QuestionIntent.DEADLINE: self._answer_deadline,
            QuestionIntent.ONGOING_CASE: self._answer_ongoing_case,
            QuestionIntent.PERSON: self._answer_person,
            QuestionIntent.DATE: self._answer_date,
            QuestionIntent.AMOUNT: self._answer_amount,
            QuestionIntent.LOCATION: self._answer_location,
        }

        handler = handlers.get(intent, self._answer_general)
        answer = handler(
            question=question,
            text=text,
            document_type=document_type,
            metadata=meta,
            verification_status=verification_status,
        )
        answer.question = question
        answer.sources = [document_id] if document_id else []

        return answer

    # ── Intent classification ────────────────────────────────────────────

    def _classify_intent(self, question: str) -> str:
        q_lower = question.lower().strip()
        for intent, patterns in _INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, q_lower):
                    return intent
        return QuestionIntent.GENERAL

    # ── Answer handlers ──────────────────────────────────────────────────

    def _answer_about(self, **kwargs) -> AssistantAnswer:
        text = kwargs["text"]
        doc_type = kwargs["document_type"]
        meta = kwargs["metadata"]

        # Extract all entities for evidence
        all_items = extract_all(text)

        doc_label = doc_type.replace("_", " ").title() if doc_type else "Unknown"

        # Build summary
        parts = [f"This document is a {doc_label}."]

        people = all_items.get("people", [])
        if people:
            names = [p.value for p in people[:3]]
            parts.append(f"It mentions: {', '.join(names)}.")

        orgs = all_items.get("organizations", [])
        if orgs:
            org_names = [o.value for o in orgs[:3]]
            parts.append(f"Organizations involved: {', '.join(org_names)}.")

        dates = all_items.get("dates", [])
        if dates:
            date_vals = [d.value for d in dates[:3]]
            parts.append(f"Key dates: {', '.join(date_vals)}.")

        cases = all_items.get("case_numbers", [])
        if cases:
            case_vals = [c.value for c in cases[:3]]
            parts.append(f"Case references: {', '.join(case_vals)}.")

        evidence = []
        for items in all_items.values():
            for item in items[:2]:
                evidence.append({
                    "type": item.category,
                    "value": item.value,
                    "snippet": item.evidence[:150],
                    "confidence": round(item.confidence, 3),
                })

        return AssistantAnswer(
            answer=" ".join(parts),
            confidence=0.80,
            evidence=evidence,
            reasoning=f"Extracted {sum(len(v) for v in all_items.values())} entities from document text to build summary.",
        )

    def _answer_department(self, **kwargs) -> AssistantAnswer:
        text = kwargs["text"]
        meta = kwargs["metadata"]

        orgs = extract_organizations(text)
        dept = meta.get("department", "")

        if dept:
            return AssistantAnswer(
                answer=f"This document was issued by: {dept}.",
                confidence=0.90,
                evidence=[{"type": "metadata", "value": dept, "snippet": f"department={dept}", "confidence": 0.90}],
                reasoning="Department identified from document metadata.",
            )

        if orgs:
            top_org = orgs[0]
            return AssistantAnswer(
                answer=f"The issuing authority appears to be: {top_org.value}.",
                confidence=top_org.confidence,
                evidence=[{"type": "organization", "value": top_org.value, "snippet": top_org.evidence, "confidence": top_org.confidence}],
                reasoning=f"Identified from document text. Found {len(orgs)} organization references.",
            )

        return AssistantAnswer(
            answer="The issuing department could not be determined from the document.",
            confidence=0.2,
            evidence=[],
            reasoning="No department metadata found and no clear organization references in text.",
        )

    def _answer_verified(self, **kwargs) -> AssistantAnswer:
        status = kwargs["verification_status"]

        status_map = {
            "verified": ("Yes, this document is verified.", 0.95),
            "pending": ("This document is pending verification.", 0.90),
            "rejected": ("This document has been rejected during verification.", 0.95),
            "expired": ("This document's verification has expired.", 0.90),
        }

        if status and status.lower() in status_map:
            answer_text, conf = status_map[status.lower()]
            return AssistantAnswer(
                answer=answer_text,
                confidence=conf,
                evidence=[{"type": "verification_status", "value": status, "snippet": f"Status: {status}", "confidence": conf}],
                reasoning=f"Verification status retrieved from document metadata: {status}.",
            )

        return AssistantAnswer(
            answer="The verification status is not available for this document.",
            confidence=0.3,
            evidence=[],
            reasoning="No verification status found in document metadata.",
        )

    def _answer_deadline(self, **kwargs) -> AssistantAnswer:
        text = kwargs["text"]
        dates = extract_dates(text)

        deadlines = [d for d in dates if d.category == "deadline"]

        if deadlines:
            main = deadlines[0]
            return AssistantAnswer(
                answer=f"The deadline is: {main.value}.",
                confidence=main.confidence,
                evidence=[{"type": "deadline", "value": main.value, "snippet": main.evidence, "confidence": main.confidence}],
                reasoning=f"Found {len(deadlines)} deadline reference(s) in document text.",
            )

        # Fallback: check for expiry dates
        expiry = [d for d in dates if "expir" in d.evidence.lower() or "valid" in d.evidence.lower()]
        if expiry:
            return AssistantAnswer(
                answer=f"No explicit deadline found, but an expiry/validity date is: {expiry[0].value}.",
                confidence=expiry[0].confidence * 0.8,
                evidence=[{"type": "expiry_date", "value": expiry[0].value, "snippet": expiry[0].evidence, "confidence": expiry[0].confidence}],
                reasoning="No deadline keyword found, but identified an expiry/validity date.",
            )

        return AssistantAnswer(
            answer="No deadline or expiry date was found in this document.",
            confidence=0.5,
            evidence=[],
            reasoning=f"Scanned document text ({len(text)} chars). No deadline or expiry keywords detected near any date.",
        )

    def _answer_ongoing_case(self, **kwargs) -> AssistantAnswer:
        text = kwargs["text"]
        text_lower = text.lower()

        cases = extract_case_numbers(text)
        case_keywords = ["ongoing", "pending", "active", "fir", "complaint", "hearing", "next date"]
        found_kw = [kw for kw in case_keywords if kw in text_lower]

        if cases and found_kw:
            case_val = cases[0].value
            return AssistantAnswer(
                answer=f"Yes, there appears to be an ongoing case: {case_val}. Keywords found: {', '.join(found_kw)}.",
                confidence=0.80,
                evidence=[
                    {"type": "case_number", "value": case_val, "snippet": cases[0].evidence, "confidence": cases[0].confidence},
                    {"type": "case_keywords", "value": ", ".join(found_kw), "snippet": "", "confidence": 0.7},
                ],
                reasoning=f"Found {len(cases)} case reference(s) and {len(found_kw)} active-case keywords.",
            )

        if cases:
            return AssistantAnswer(
                answer=f"A case reference was found ({cases[0].value}), but it's unclear if it's currently active.",
                confidence=0.5,
                evidence=[{"type": "case_number", "value": cases[0].value, "snippet": cases[0].evidence, "confidence": cases[0].confidence}],
                reasoning="Case number found but no active/pending keywords detected.",
            )

        return AssistantAnswer(
            answer="No ongoing case references were found in this document.",
            confidence=0.6,
            evidence=[],
            reasoning="No case numbers or active-case keywords found in document text.",
        )

    def _answer_person(self, **kwargs) -> AssistantAnswer:
        text = kwargs["text"]
        from ai_engine.extractors import extract_people

        people = extract_people(text)
        if people:
            names = [p.value for p in people]
            evidence = [{"type": "person", "value": p.value, "snippet": p.evidence, "confidence": p.confidence} for p in people[:5]]
            return AssistantAnswer(
                answer=f"The following people are mentioned: {', '.join(names[:5])}{'...' if len(names) > 5 else ''}.",
                confidence=0.80,
                evidence=evidence,
                reasoning=f"Extracted {len(people)} person names from document text.",
            )

        return AssistantAnswer(
            answer="No person names could be extracted from this document.",
            confidence=0.4,
            evidence=[],
            reasoning="No name patterns (label: Name, S/o, title) found in text.",
        )

    def _answer_date(self, **kwargs) -> AssistantAnswer:
        text = kwargs["text"]
        dates = extract_dates(text)

        if dates:
            evidence = [{"type": d.category, "value": d.value, "snippet": d.evidence, "confidence": d.confidence} for d in dates[:5]]
            date_list = ", ".join(d.value for d in dates[:5])
            return AssistantAnswer(
                answer=f"Important dates found: {date_list}.",
                confidence=0.85,
                evidence=evidence,
                reasoning=f"Extracted {len(dates)} date references from document.",
            )

        return AssistantAnswer(
            answer="No dates were found in this document.",
            confidence=0.5,
            evidence=[],
            reasoning="No date patterns found in document text.",
        )

    def _answer_amount(self, **kwargs) -> AssistantAnswer:
        text = kwargs["text"]
        from ai_engine.extractors import extract_amounts

        amounts = extract_amounts(text)
        if amounts:
            evidence = [{"type": "amount", "value": a.value, "snippet": a.evidence, "confidence": a.confidence} for a in amounts[:5]]
            amt_list = ", ".join(a.value for a in amounts[:5])
            return AssistantAnswer(
                answer=f"Amounts found: {amt_list}.",
                confidence=0.85,
                evidence=evidence,
                reasoning=f"Extracted {len(amounts)} monetary amounts from document.",
            )

        return AssistantAnswer(
            answer="No monetary amounts were found in this document.",
            confidence=0.5,
            evidence=[],
            reasoning="No currency/amount patterns found in text.",
        )

    def _answer_location(self, **kwargs) -> AssistantAnswer:
        text = kwargs["text"]
        from ai_engine.extractors import extract_locations

        locs = extract_locations(text)
        if locs:
            evidence = [{"type": "location", "value": l.value, "snippet": l.evidence, "confidence": l.confidence} for l in locs[:5]]
            loc_list = ", ".join(l.value for l in locs[:5])
            return AssistantAnswer(
                answer=f"Locations found: {loc_list}.",
                confidence=0.75,
                evidence=evidence,
                reasoning=f"Extracted {len(locs)} location references from document.",
            )

        return AssistantAnswer(
            answer="No specific locations could be extracted from this document.",
            confidence=0.4,
            evidence=[],
            reasoning="No location patterns found in text.",
        )

    def _answer_general(self, **kwargs) -> AssistantAnswer:
        """Fallback: try to answer using full extraction."""
        text = kwargs["text"]
        question = kwargs.get("question", "")
        all_items = extract_all(text)

        # Find items matching keywords in the question
        q_lower = question.lower()
        relevant = []
        for category, items in all_items.items():
            for item in items:
                if any(word in item.value.lower() or word in item.evidence.lower()
                       for word in q_lower.split() if len(word) > 3):
                    relevant.append(item)

        if relevant:
            evidence = [{"type": r.category, "value": r.value, "snippet": r.evidence, "confidence": r.confidence} for r in relevant[:5]]
            vals = [r.value for r in relevant[:5]]
            return AssistantAnswer(
                answer=f"Based on the document, relevant information found: {', '.join(vals)}.",
                confidence=0.6,
                evidence=evidence,
                reasoning=f"Matched {len(relevant)} extracted items to question keywords.",
            )

        return AssistantAnswer(
            answer="I could not find specific information to answer this question from the document.",
            confidence=0.2,
            evidence=[],
            reasoning="No extracted entities matched the question keywords.",
        )
