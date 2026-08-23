"""
ai_engine/routes.py -- FastAPI endpoints for the AI Intelligence Layer.

Endpoints:
  POST /ai/summarize     — Generate document summary with entity extraction
  POST /ai/entities      — Extract classified entities (citizens, officers, etc.)
  POST /ai/timeline      — Generate chronological timeline of events
  POST /ai/case-intel    — Cross-document case intelligence
  POST /assistant/ask    — Evidence-backed Q&A assistant
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai_engine.assistant import AIAssistant
from ai_engine.case_intelligence import CaseIntelligence
from ai_engine.entities import EntityExtractor
from ai_engine.summarizer import DocumentSummarizer
from ai_engine.timeline import TimelineExtractor

logger = logging.getLogger(__name__)


# ── Request models ───────────────────────────────────────────────────────────

class SummarizeRequest(BaseModel):
    text: str = Field(..., description="Document text (OCR or extracted)")
    document_id: str = ""
    document_type: str = ""
    source: str = ""
    max_key_points: int = Field(10, ge=1, le=30)


class EntitiesRequest(BaseModel):
    text: str = Field(..., description="Document text")
    document_id: str = ""
    document_type: str = ""
    source: str = ""


class TimelineRequest(BaseModel):
    text: str = Field(..., description="Document text")
    source: str = ""
    document_type: str = ""


class CaseIntelRequest(BaseModel):
    documents: List[Dict[str, Any]] = Field(
        ...,
        description="List of documents, each with 'id', 'text', and optional 'metadata'",
    )


class AskRequest(BaseModel):
    question: str = Field(..., description="Question to ask about the document")
    text: str = Field(..., description="Document text")
    document_id: str = ""
    document_type: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)
    verification_status: str = ""


# ── Router factory ───────────────────────────────────────────────────────────

def create_ai_router() -> APIRouter:
    """Create and return the AI Intelligence API router."""

    ai_router = APIRouter(prefix="/ai", tags=["AI Intelligence"])
    assistant_router = APIRouter(prefix="/assistant", tags=["AI Assistant"])

    summarizer = DocumentSummarizer()
    entity_extractor = EntityExtractor()
    timeline_extractor = TimelineExtractor()
    case_intel = CaseIntelligence()
    assistant = AIAssistant()

    # ── POST /ai/summarize ───────────────────────────────────────────────

    @ai_router.post("/summarize", summary="Generate document summary with entity extraction")
    async def summarize_document(body: SummarizeRequest) -> Dict[str, Any]:
        """
        Generate a comprehensive summary of a government document.

        Extracts:
        - Key points (scored by importance)
        - Important dates & deadlines
        - Organizations & departments
        - People (citizens, officers)
        - Locations
        - Monetary amounts
        - Case numbers & references

        Every extracted item includes evidence (verbatim snippet) and confidence score.
        """
        if not body.text or len(body.text.strip()) < 10:
            raise HTTPException(400, "Document text is too short to summarize")

        try:
            summary = summarizer.summarize(
                text=body.text,
                document_id=body.document_id,
                document_type=body.document_type,
                source=body.source,
                max_key_points=body.max_key_points,
            )
            return {
                "status": "success",
                "summary": summary.to_dict(),
            }
        except Exception as e:
            logger.error("Summarization failed: %s", e, exc_info=True)
            raise HTTPException(500, f"Summarization failed: {e}")

    # ── POST /ai/entities ────────────────────────────────────────────────

    @ai_router.post("/entities", summary="Extract classified government entities")
    async def extract_entities(body: EntitiesRequest) -> Dict[str, Any]:
        """
        Extract and classify entities from government documents.

        Generates profiles for:
        - **Citizens**: applicants, petitioners, respondents
        - **Officers**: judges, inspectors, collectors, registrars
        - **Departments**: ministries, directorates, boards
        - **Courts**: high courts, district courts, tribunals
        - **Institutions**: universities, schools, hospitals

        Each entity includes name, type, role, confidence, and evidence.
        """
        if not body.text or len(body.text.strip()) < 10:
            raise HTTPException(400, "Document text is too short for entity extraction")

        try:
            entities = entity_extractor.extract(
                text=body.text,
                document_id=body.document_id,
                document_type=body.document_type,
                source=body.source,
            )

            # Convert to dicts
            result = {}
            total = 0
            for category, profiles in entities.items():
                result[category] = [p.to_dict() for p in profiles]
                total += len(profiles)

            return {
                "status": "success",
                "entities": result,
                "total_count": total,
            }
        except Exception as e:
            logger.error("Entity extraction failed: %s", e, exc_info=True)
            raise HTTPException(500, f"Entity extraction failed: {e}")

    # ── POST /ai/timeline ────────────────────────────────────────────────

    @ai_router.post("/timeline", summary="Generate chronological timeline of events")
    async def extract_timeline(body: TimelineRequest) -> Dict[str, Any]:
        """
        Extract chronological events from a government document.

        Each event includes:
        - Date (original + ISO parsed)
        - Description (what happened)
        - Event type (filing, issuance, hearing, deadline, etc.)
        - Confidence and evidence

        Events are returned in chronological order.
        """
        if not body.text or len(body.text.strip()) < 10:
            raise HTTPException(400, "Document text is too short for timeline extraction")

        try:
            events = timeline_extractor.extract(
                text=body.text,
                source=body.source,
                document_type=body.document_type,
            )

            return {
                "status": "success",
                "timeline": [e.to_dict() for e in events],
                "event_count": len(events),
            }
        except Exception as e:
            logger.error("Timeline extraction failed: %s", e, exc_info=True)
            raise HTTPException(500, f"Timeline extraction failed: {e}")

    # ── POST /ai/case-intel ──────────────────────────────────────────────

    @ai_router.post("/case-intel", summary="Cross-document case intelligence analysis")
    async def analyze_case_intelligence(body: CaseIntelRequest) -> Dict[str, Any]:
        """
        Analyze multiple documents for cross-document intelligence.

        Detects:
        - **Related cases**: shared parties, case references, connected facts
        - **Duplicate identities**: same person across documents (exact + fuzzy)
        - **Conflicting records**: contradictory data across documents

        Requires at least 2 documents.
        Each document should have 'id' and 'text' fields, with optional 'metadata'.
        """
        if len(body.documents) < 2:
            raise HTTPException(400, "At least 2 documents are required for case intelligence")

        for doc in body.documents:
            if not doc.get("id") or not doc.get("text"):
                raise HTTPException(400, "Each document must have 'id' and 'text' fields")

        try:
            result = case_intel.analyze(body.documents)
            return {
                "status": "success",
                "intelligence": result.to_dict(),
            }
        except Exception as e:
            logger.error("Case intelligence failed: %s", e, exc_info=True)
            raise HTTPException(500, f"Case intelligence analysis failed: {e}")

    # ── POST /assistant/ask ──────────────────────────────────────────────

    @assistant_router.post("/ask", summary="Ask a question about a document (evidence-backed)")
    async def ask_question(body: AskRequest) -> Dict[str, Any]:
        """
        Ask a question about a government document.

        The AI assistant answers with evidence from the document text.

        Example questions:
        - What is this document about?
        - Which department issued it?
        - Is it verified?
        - What is the deadline?
        - Is there an ongoing case?
        - Who are the people mentioned?
        - What are the important dates?

        Every answer includes:
        - **answer**: the response text
        - **confidence**: how certain the answer is (0-1)
        - **evidence**: verbatim snippets from the document
        - **reasoning**: why this answer was given
        """
        if not body.question or len(body.question.strip()) < 3:
            raise HTTPException(400, "Question is too short")
        if not body.text or len(body.text.strip()) < 10:
            raise HTTPException(400, "Document text is too short")

        try:
            answer = assistant.ask(
                question=body.question,
                text=body.text,
                document_id=body.document_id,
                document_type=body.document_type,
                metadata=body.metadata,
                verification_status=body.verification_status,
            )
            return {
                "status": "success",
                "answer": answer.to_dict(),
            }
        except Exception as e:
            logger.error("Assistant failed: %s", e, exc_info=True)
            raise HTTPException(500, f"Assistant error: {e}")

    return ai_router, assistant_router
