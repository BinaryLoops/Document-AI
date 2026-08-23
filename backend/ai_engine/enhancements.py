"""
ai_engine/enhancements.py -- Enhancements to existing AI modules.

Preserves OCR, RAG, FAISS, Knowledge Graph.

Adds:
  1. AdaptiveChunker       — document-type-aware chunking strategy
  2. MetadataConfidence    — confidence scoring for extracted metadata fields
  3. SourceRanker          — source relevance ranking with recency decay
  4. CrossDocumentLinker   — entity-based cross-document linking
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Adaptive Chunker
# ─────────────────────────────────────────────────────────────────────────────

class AdaptiveChunker:
    """
    Document-type-aware chunking strategy.

    Different document types have different structural patterns.
    Legal docs: paragraphs + numbered clauses.
    Certificates: small, dense.
    FIRs: narrative paragraphs.
    Land records: tabular.

    This class selects chunk size, overlap, and split strategy based on
    the detected document type and content structure.
    """

    # Document type -> (chunk_size, overlap, strategy)
    _STRATEGIES = {
        "passport":              (500,  100, "paragraph"),
        "driving_licence":       (400,  80,  "paragraph"),
        "birth_certificate":     (500,  100, "paragraph"),
        "income_certificate":    (600,  120, "paragraph"),
        "land_record":           (800,  150, "section"),
        "education_certificate": (500,  100, "paragraph"),
        "fir":                   (1000, 200, "paragraph"),
        "court_order":           (1200, 250, "section"),
        "stamp_paper":           (600,  120, "paragraph"),
    }

    # Default fallback
    _DEFAULT = (800, 160, "paragraph")

    def get_strategy(
        self,
        document_type: str,
        text: str = "",
    ) -> Dict[str, Any]:
        """
        Get optimal chunking strategy for a document type.

        Returns dict with:
          chunk_size, chunk_overlap, strategy, section_markers
        """
        base = self._STRATEGIES.get(document_type, self._DEFAULT)
        chunk_size, overlap, strategy = base

        # Adaptive: adjust based on actual text length
        text_len = len(text)
        if text_len < 500:
            # Very short document -> single chunk
            return {
                "chunk_size": text_len + 1,
                "chunk_overlap": 0,
                "strategy": "whole",
                "section_markers": [],
            }
        elif text_len > 10000:
            # Very long -> increase chunk size for efficiency
            chunk_size = int(chunk_size * 1.5)
            overlap = int(overlap * 1.3)

        # Detect section markers
        section_markers = self._detect_sections(text) if strategy == "section" else []

        return {
            "chunk_size": chunk_size,
            "chunk_overlap": overlap,
            "strategy": strategy,
            "section_markers": section_markers,
        }

    def chunk(
        self,
        text: str,
        document_type: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Chunk text using adaptive strategy.

        Returns list of dicts: {text, chunk_index, start_char, end_char, strategy}
        """
        strategy = self.get_strategy(document_type, text)
        strat_name = strategy["strategy"]

        if strat_name == "whole":
            return [{
                "text": text,
                "chunk_index": 0,
                "start_char": 0,
                "end_char": len(text),
                "strategy": "whole",
            }]

        if strat_name == "section" and strategy["section_markers"]:
            return self._chunk_by_sections(text, strategy)

        return self._chunk_by_paragraph(text, strategy)

    def _detect_sections(self, text: str) -> List[int]:
        """Detect section boundaries in legal documents."""
        markers = []
        patterns = [
            r'^(?:Section|SECTION|Para|PARA|Article|ARTICLE|Clause|CLAUSE)\s+\d+',
            r'^\d+\.\s+[A-Z]',
            r'^[IVXLCDM]+\.\s+',
            r'^(?:ORDER|JUDGMENT|DECREE|WHEREAS|NOW THEREFORE)',
        ]
        for i, line in enumerate(text.split("\n")):
            line = line.strip()
            for pat in patterns:
                if re.match(pat, line):
                    # Find char position
                    pos = text.find(line)
                    if pos >= 0 and pos not in markers:
                        markers.append(pos)
                    break

        return sorted(markers)

    def _chunk_by_sections(
        self, text: str, strategy: Dict
    ) -> List[Dict[str, Any]]:
        """Chunk using detected section boundaries."""
        markers = strategy["section_markers"] + [len(text)]
        chunks = []
        prev = 0

        for i, pos in enumerate(markers):
            section = text[prev:pos].strip()
            if section:
                # If section is too large, sub-chunk it
                if len(section) > strategy["chunk_size"] * 2:
                    sub_chunks = self._split_text(
                        section, strategy["chunk_size"], strategy["chunk_overlap"]
                    )
                    for sc in sub_chunks:
                        chunks.append({
                            "text": sc,
                            "chunk_index": len(chunks),
                            "start_char": prev + section.find(sc[:50]),
                            "end_char": prev + section.find(sc[:50]) + len(sc),
                            "strategy": "section",
                        })
                else:
                    chunks.append({
                        "text": section,
                        "chunk_index": len(chunks),
                        "start_char": prev,
                        "end_char": pos,
                        "strategy": "section",
                    })
            prev = pos

        return chunks if chunks else self._chunk_by_paragraph(text, strategy)

    def _chunk_by_paragraph(
        self, text: str, strategy: Dict
    ) -> List[Dict[str, Any]]:
        """Chunk by paragraph boundaries, respecting chunk size."""
        chunk_size = strategy["chunk_size"]
        overlap = strategy["chunk_overlap"]

        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        current = ""
        start = 0
        pos = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                pos += 2
                continue

            if len(current) + len(para) + 1 > chunk_size and current:
                chunks.append({
                    "text": current.strip(),
                    "chunk_index": len(chunks),
                    "start_char": start,
                    "end_char": pos,
                    "strategy": "paragraph",
                })
                # Apply overlap
                if overlap > 0 and len(current) > overlap:
                    overlap_text = current[-overlap:]
                    current = overlap_text + "\n\n" + para
                    start = pos - overlap
                else:
                    current = para
                    start = pos
            else:
                if current:
                    current += "\n\n" + para
                else:
                    current = para
                    start = pos

            pos += len(para) + 2

        if current.strip():
            chunks.append({
                "text": current.strip(),
                "chunk_index": len(chunks),
                "start_char": start,
                "end_char": pos,
                "strategy": "paragraph",
            })

        return chunks

    def _split_text(self, text: str, size: int, overlap: int) -> List[str]:
        """Simple fixed-size split with overlap."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - overlap if overlap > 0 else end
        return chunks


# ─────────────────────────────────────────────────────────────────────────────
# 2. Metadata Confidence Scorer
# ─────────────────────────────────────────────────────────────────────────────

class MetadataConfidence:
    """
    Score confidence of extracted metadata fields.

    Considers:
      - Extraction method (OCR vs direct vs regex)
      - Consistency across chunks
      - Pattern match strength
      - Cross-reference with other fields
    """

    def score_field(
        self,
        field_name: str,
        value: str,
        extraction_method: str = "regex",
        occurrences: int = 1,
        total_chunks: int = 1,
        expected_pattern: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Score confidence for a single metadata field.

        Returns:
            Dict with confidence, evidence, method, factors.
        """
        base = self._method_confidence(extraction_method)
        consistency = min(occurrences / max(total_chunks, 1), 1.0)
        pattern_score = self._pattern_match_score(value, expected_pattern) if expected_pattern else 0.5

        # Weighted combination
        confidence = (base * 0.4) + (consistency * 0.3) + (pattern_score * 0.3)

        return {
            "field": field_name,
            "value": value,
            "confidence": round(confidence, 3),
            "method": extraction_method,
            "factors": {
                "method_score": round(base, 3),
                "consistency_score": round(consistency, 3),
                "pattern_score": round(pattern_score, 3),
                "occurrences": occurrences,
            },
        }

    def score_metadata(
        self,
        metadata: Dict[str, Any],
        extraction_methods: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Score all fields in a metadata dict."""
        methods = extraction_methods or {}
        scored = {}

        for key, value in metadata.items():
            if not value or key.startswith("_"):
                continue
            method = methods.get(key, "regex")
            scored[key] = self.score_field(key, str(value), method)

        overall = sum(s["confidence"] for s in scored.values()) / max(len(scored), 1)
        return {
            "fields": scored,
            "overall_confidence": round(overall, 3),
            "total_fields": len(scored),
        }

    def _method_confidence(self, method: str) -> float:
        return {
            "direct":   0.95,  # Direct API / database lookup
            "ocr":      0.70,  # OCR extraction
            "regex":    0.75,  # Regex pattern matching
            "ner":      0.80,  # NLP Named Entity Recognition
            "llm":      0.65,  # LLM extraction (can hallucinate)
            "manual":   0.99,  # Human-entered
        }.get(method.lower(), 0.50)

    def _pattern_match_score(self, value: str, pattern: str) -> float:
        try:
            if re.fullmatch(pattern, value):
                return 1.0
            elif re.search(pattern, value):
                return 0.7
            else:
                return 0.2
        except re.error:
            return 0.5


# ─────────────────────────────────────────────────────────────────────────────
# 3. Source Ranker
# ─────────────────────────────────────────────────────────────────────────────

class SourceRanker:
    """
    Rank document sources by relevance with recency decay.

    Factors:
      - Semantic similarity score (from FAISS/RAG)
      - Source authority (government > private)
      - Recency (newer documents score higher)
      - Verification status (verified > unverified)
    """

    # Authority weights by source type
    _AUTHORITY_WEIGHTS = {
        "government":  1.0,
        "court":       0.95,
        "tribunal":    0.90,
        "authority":   0.85,
        "official":    0.80,
        "certified":   0.75,
        "private":     0.50,
        "unknown":     0.30,
    }

    def rank(
        self,
        sources: List[Dict[str, Any]],
        query: str = "",
        current_time: Optional[datetime] = None,
        decay_days: int = 365,
    ) -> List[Dict[str, Any]]:
        """
        Rank sources by composite score.

        Each source dict should have:
          - score: float (similarity score)
          - metadata: dict with optional keys:
            source_type, uploaded_at, verification_status

        Returns sorted list with added 'rank_score' field.
        """
        now = current_time or datetime.now(timezone.utc)

        ranked = []
        for src in sources:
            meta = src.get("metadata", {})
            sim_score = float(src.get("score", 0.0))

            # Authority factor
            source_type = meta.get("source_type", "unknown").lower()
            authority = self._AUTHORITY_WEIGHTS.get(source_type, 0.30)

            # Recency factor
            upload_str = meta.get("uploaded_at", "")
            recency = self._recency_score(upload_str, now, decay_days)

            # Verification factor
            verification = meta.get("verification_status", "")
            verify_boost = 1.0 if verification == "verified" else 0.8

            # Composite score
            rank_score = (
                sim_score * 0.40
                + authority * 0.25
                + recency * 0.20
                + verify_boost * 0.15
            )

            ranked.append({
                **src,
                "rank_score": round(rank_score, 4),
                "factors": {
                    "similarity": round(sim_score, 4),
                    "authority": round(authority, 3),
                    "recency": round(recency, 3),
                    "verification": round(verify_boost, 3),
                },
            })

        ranked.sort(key=lambda x: x["rank_score"], reverse=True)
        return ranked

    def _recency_score(
        self, date_str: str, now: datetime, decay_days: int
    ) -> float:
        if not date_str:
            return 0.5
        try:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            days_old = (now - dt).days
            # Exponential decay
            return math.exp(-days_old / max(decay_days, 1))
        except (ValueError, TypeError):
            return 0.5


# ─────────────────────────────────────────────────────────────────────────────
# 4. Cross-Document Linker
# ─────────────────────────────────────────────────────────────────────────────

class CrossDocumentLinker:
    """
    Link entities across multiple documents.

    Builds an entity graph where nodes are (entity, document) pairs
    and edges represent cross-document relationships.
    """

    # Threshold for fuzzy name matching
    MATCH_THRESHOLD = 80

    def link(
        self,
        documents: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build cross-document entity links.

        Args:
            documents: List of dicts with keys: id, text, metadata, entities

        Returns:
            Dict with links, entity_graph, shared_entities.
        """
        from ai_engine.extractors import extract_people, extract_organizations

        # Extract entities per document
        doc_entities: Dict[str, Dict[str, List]] = {}
        for doc in documents:
            doc_id = doc.get("id", "")
            text = doc.get("text", "")
            doc_entities[doc_id] = {
                "people": [p.value for p in extract_people(text, doc_id)],
                "organizations": [o.value for o in extract_organizations(text, doc_id)],
            }

        # Find cross-document links
        links = []
        shared = defaultdict(list)
        doc_ids = list(doc_entities.keys())

        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                a_id, b_id = doc_ids[i], doc_ids[j]
                a_ents = doc_entities[a_id]
                b_ents = doc_entities[b_id]

                # People links
                for a_name in a_ents["people"]:
                    for b_name in b_ents["people"]:
                        score = fuzz.ratio(a_name.lower(), b_name.lower())
                        if score >= self.MATCH_THRESHOLD:
                            link = {
                                "entity": a_name,
                                "entity_type": "person",
                                "document_a": a_id,
                                "document_b": b_id,
                                "match_score": score / 100,
                                "match_type": "exact" if score == 100 else "fuzzy",
                            }
                            links.append(link)
                            shared[a_name.lower()].extend([a_id, b_id])

                # Organization links
                for a_org in a_ents["organizations"]:
                    for b_org in b_ents["organizations"]:
                        score = fuzz.ratio(a_org.lower(), b_org.lower())
                        if score >= self.MATCH_THRESHOLD:
                            link = {
                                "entity": a_org,
                                "entity_type": "organization",
                                "document_a": a_id,
                                "document_b": b_id,
                                "match_score": score / 100,
                                "match_type": "exact" if score == 100 else "fuzzy",
                            }
                            links.append(link)
                            shared[a_org.lower()].extend([a_id, b_id])

        # Deduplicate shared entity doc refs
        shared_entities = {
            name: list(set(doc_ids))
            for name, doc_ids in shared.items()
        }

        logger.info(
            "Cross-document linking: %d links, %d shared entities across %d documents",
            len(links), len(shared_entities), len(doc_ids),
        )

        return {
            "links": links,
            "shared_entities": shared_entities,
            "total_links": len(links),
            "documents_analyzed": len(doc_ids),
        }
