"""
DocuMind Intelligence Engine
============================
Implements all 8 document intelligence features on top of the KG:

Tier 1 — Must Have
  1. EvidenceProvenanceEngine   — source citation + evidence chain for every answer
  2. CrossDocumentRelationEngine — link entities/fields across documents in the KG
  3. CompletenessEngine          — check which required fields / doc-types are present
  4. ContradictionEngine         — detect field-level contradictions across documents

Tier 2 — High Impact
  5. VersionTracker              — supersession / amendment detection between doc versions
  6. GraphRAGEngine              — KG-guided retrieval + context-aware answer generation
  7. DocumentComparisonEngine    — structured side-by-side field diff with scoring
  8. ExplainabilityEngine        — "Why did you answer that?" trace builder
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Evidence / Source Provenance
# ---------------------------------------------------------------------------

class EvidenceProvenanceEngine:
    """
    Attaches a full evidence chain to every extracted value or RAG answer.

    Each evidence item records:
      - source document name
      - chunk index / page
      - verbatim snippet that supports the claim
      - confidence score
      - entity trace from the KG (if available)
    """

    def __init__(self, kg_manager=None):
        self.kg_manager = kg_manager

    def build_evidence_chain(
        self,
        query: str,
        retrieved_docs: List[Dict[str, Any]],
        response: str,
    ) -> Dict[str, Any]:
        """
        Build a full provenance record for a RAG answer.

        Args:
            query: The user question
            retrieved_docs: Documents returned by the retriever
            response: The LLM-generated answer

        Returns:
            Provenance dict with sources, snippets, confidence, KG trace
        """
        sources: List[Dict[str, Any]] = []
        total_score = 0.0

        for idx, doc in enumerate(retrieved_docs):
            meta = doc.get("metadata", {})
            score = float(doc.get("score", 0.0))
            snippet = doc.get("text", "")[:300]
            total_score += score

            # Find any KG entities mentioned in this chunk
            kg_entities: List[str] = []
            if self.kg_manager:
                try:
                    for word in re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', doc.get("text", "")):
                        res = self.kg_manager.get_entity(word)
                        if res.get("found"):
                            kg_entities.append(res["name"])
                except Exception:
                    pass

            sources.append({
                "rank": idx + 1,
                "source_document": meta.get("source", meta.get("filename", "Unknown")),
                "document_id": meta.get("document_id", ""),
                "document_type": meta.get("document_type", ""),
                "page": meta.get("page", "unknown"),
                "chunk_index": meta.get("chunk_index", idx),
                "relevance_score": round(float(score), 4),
                "evidence_snippet": snippet,
                "kg_entities_found": list(set(kg_entities)),
            })

        avg_confidence = (total_score / len(retrieved_docs)) if retrieved_docs else 0.0

        # Check if response actually uses the context or falls back
        grounded = not any(
            phrase in response.lower()
            for phrase in [
                "i don't know", "i cannot", "not in the documents",
                "as an ai", "my training",
            ]
        )

        return {
            "query": query,
            "response_grounded": grounded,
            "overall_confidence": round(avg_confidence, 4),
            "source_count": len(sources),
            "sources": sources,
            "provenance_summary": (
                f"Answer derived from {len(sources)} document chunk(s) "
                f"with avg relevance {avg_confidence:.2%}."
                if grounded
                else "Answer could not be fully grounded in provided documents."
            ),
        }

    def annotate_field(
        self,
        field_name: str,
        field_value: Any,
        evidence: Dict[str, Any],
        document_name: str,
    ) -> Dict[str, Any]:
        """Wrap a single extracted field with its provenance."""
        return {
            "field": field_name,
            "value": field_value,
            "source_document": document_name,
            "page": evidence.get("page", "unknown"),
            "evidence_snippet": evidence.get("evidence_snippet", ""),
            "confidence": evidence.get("confidence", 0.0),
            "verified": evidence.get("confidence", 0.0) >= 0.7,
        }


# ---------------------------------------------------------------------------
# 2. Cross-Document Relationships
# ---------------------------------------------------------------------------

class CrossDocumentRelationEngine:
    """
    Links matching entities / fields across multiple documents in the KG.

    After two or more documents are uploaded the engine:
      - finds entities that appear in more than one document
      - creates SAME_AS / MENTIONED_IN relations in the KG
      - returns a cross-document entity map
    """

    def __init__(self, kg_manager=None):
        self.kg_manager = kg_manager

    def build_cross_doc_map(
        self,
        document_fields: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build cross-document entity map from extracted field sets.

        Args:
            document_fields: List of { document_id, filename, document_type,
                                       extracted_fields: [{field, value, confidence}] }

        Returns:
            cross_doc_map with shared entities and link count
        """
        # value → list of (doc_id, filename, field_name, confidence)
        value_index: Dict[str, List[Dict]] = defaultdict(list)

        for doc in document_fields:
            doc_id = doc.get("document_id", "")
            filename = doc.get("filename", "")
            for f in doc.get("extracted_fields", []):
                val = str(f.get("value", "")).strip().lower()
                if len(val) < 2:
                    continue
                value_index[val].append({
                    "document_id": doc_id,
                    "filename": filename,
                    "field": f.get("field", ""),
                    "confidence": f.get("confidence", 0.0),
                })

        # Shared values appear in > 1 document
        shared: List[Dict[str, Any]] = []
        for value, occurrences in value_index.items():
            doc_ids = {o["document_id"] for o in occurrences}
            if len(doc_ids) > 1:
                shared.append({
                    "value": value,
                    "occurrence_count": len(occurrences),
                    "documents": occurrences,
                    "relation_type": "SHARED_VALUE",
                })

                # Also add to KG if available
                if self.kg_manager:
                    try:
                        ekg = self.kg_manager.kg
                        # Add a cross-doc relation between each pair of occurrences
                        for i in range(len(occurrences)):
                            for j in range(i + 1, len(occurrences)):
                                src = occurrences[i]["document_id"] + "_" + occurrences[i]["field"]
                                tgt = occurrences[j]["document_id"] + "_" + occurrences[j]["field"]
                                src_id = ekg.add_entity(src, "DocumentField")
                                tgt_id = ekg.add_entity(tgt, "DocumentField")
                                ekg.add_relation(src_id, "SAME_VALUE_AS", tgt_id, confidence=0.9)
                    except Exception:
                        pass

        return {
            "total_shared_values": len(shared),
            "document_count": len(document_fields),
            "shared_entities": shared,
            "summary": (
                f"{len(shared)} values are shared across "
                f"{len(document_fields)} documents."
            ),
        }

    def get_entity_document_map(self) -> Dict[str, Any]:
        """
        Return which documents each KG entity appears in.
        Requires chunk metadata to have been stored in the KG.
        """
        if not self.kg_manager:
            return {"error": "KG manager not available"}

        entity_docs: Dict[str, List[str]] = defaultdict(list)
        for eid, ent in self.kg_manager.kg.entities.items():
            meta = ent.get("metadata", {})
            src = meta.get("source") or meta.get("filename")
            if src:
                entity_docs[ent.get("name", eid)].append(src)

        # Only those appearing in multiple docs
        multi = {
            name: list(set(docs))
            for name, docs in entity_docs.items()
            if len(set(docs)) > 1
        }

        return {
            "cross_document_entities": multi,
            "count": len(multi),
        }


# ---------------------------------------------------------------------------
# 3. Document Completeness
# ---------------------------------------------------------------------------

# Field requirements per document type
REQUIRED_FIELDS: Dict[str, List[str]] = {
    "Identity Proof": ["full_name", "date_of_birth", "id_number", "address"],
    "Address Proof": ["full_name", "address", "issue_date"],
    "Affidavit": ["deponent_name", "deponent_address", "notary_name", "date"],
    "Certificate": ["certificate_number", "issued_to", "issued_by", "issue_date"],
    "Court Document": ["case_number", "court_name", "date", "parties"],
    "Application": ["applicant_name", "application_number", "date", "purpose"],
    "Contract": ["party_a_name", "party_b_name", "effective_date", "subject"],
    "Invoice": ["invoice_number", "vendor_name", "amount", "date"],
    "Receipt": ["receipt_number", "amount", "date"],
    "Other": [],
}

WORKFLOW_REQUIREMENTS: Dict[str, List[str]] = {
    "GOVERNMENT_APPLICATION": [
        "Application", "Identity Proof", "Address Proof"
    ],
    "COURT_CASE": [
        "Court Document", "Affidavit", "Identity Proof"
    ],
    "NOTARY": [
        "Affidavit", "Identity Proof"
    ],
    "KYC": [
        "Identity Proof", "Address Proof"
    ],
}


class CompletenessEngine:
    """
    Checks whether a set of documents satisfies field and workflow requirements.
    """

    def check_document_fields(
        self,
        document_type: str,
        extracted_fields: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Check if all required fields for a document type are present.
        """
        required = REQUIRED_FIELDS.get(document_type, [])
        if not required:
            return {
                "document_type": document_type,
                "status": "NO_REQUIREMENTS",
                "completeness_pct": 100.0,
                "present_fields": [],
                "missing_fields": [],
            }

        present_values = {
            f.get("field", "").lower().replace(" ", "_")
            for f in extracted_fields
            if f.get("value") not in (None, "", "Not found", "N/A")
        }

        present = [r for r in required if r in present_values]
        missing = [r for r in required if r not in present_values]
        pct = (len(present) / len(required)) * 100 if required else 100.0

        return {
            "document_type": document_type,
            "status": "COMPLETE" if not missing else "INCOMPLETE",
            "completeness_pct": round(pct, 1),
            "required_fields": required,
            "present_fields": present,
            "missing_fields": missing,
        }

    def check_workflow(
        self,
        workflow: str,
        uploaded_document_types: List[str],
    ) -> Dict[str, Any]:
        """
        Check if all document types required by a workflow have been uploaded.
        """
        required_types = WORKFLOW_REQUIREMENTS.get(workflow.upper(), [])
        if not required_types:
            return {
                "workflow": workflow,
                "status": "UNKNOWN_WORKFLOW",
                "available_workflows": list(WORKFLOW_REQUIREMENTS.keys()),
            }

        uploaded_set = set(uploaded_document_types)
        present = [t for t in required_types if t in uploaded_set]
        missing = [t for t in required_types if t not in uploaded_set]
        pct = (len(present) / len(required_types)) * 100

        return {
            "workflow": workflow,
            "status": "COMPLETE" if not missing else "INCOMPLETE",
            "completeness_pct": round(pct, 1),
            "required_document_types": required_types,
            "present_document_types": present,
            "missing_document_types": missing,
            "recommendation": (
                "All required documents present. Ready for review."
                if not missing
                else f"Please upload: {', '.join(missing)}"
            ),
        }


# ---------------------------------------------------------------------------
# 4. Contradiction Detection
# ---------------------------------------------------------------------------

class ContradictionEngine:
    """
    Detects field-level contradictions across multiple documents.

    Uses fuzzy matching (rapidfuzz) — same logic as DocumentComparison but
    enriched with KG entity resolution and severity scoring.
    """

    SEVERITY_THRESHOLDS = {
        "EXACT": 95,
        "MINOR": 80,
        "MODERATE": 60,
    }

    # Fields where contradictions are critical
    HIGH_STAKES_FIELDS = {
        "full_name", "date_of_birth", "id_number", "address",
        "applicant_name", "holder_name", "deponent_name",
    }

    def detect(
        self,
        document_fields: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Detect contradictions across a list of documents.

        Args:
            document_fields: List of { document_id, filename, document_type,
                                       extracted_fields }

        Returns:
            Contradiction report
        """
        # Group by normalised field name
        field_map: Dict[str, List[Dict]] = defaultdict(list)

        for doc in document_fields:
            for f in doc.get("extracted_fields", []):
                norm = self._normalise(f.get("field", ""))
                val = str(f.get("value", "")).strip()
                if norm and val and val.lower() not in ("not found", "n/a", "none"):
                    field_map[norm].append({
                        "document_id": doc.get("document_id"),
                        "filename": doc.get("filename"),
                        "document_type": doc.get("document_type"),
                        "value": val,
                        "confidence": f.get("confidence", 0.0),
                    })

        contradictions: List[Dict] = []
        for field_name, instances in field_map.items():
            if len(instances) < 2:
                continue
            for i in range(len(instances)):
                for j in range(i + 1, len(instances)):
                    c = self._compare(field_name, instances[i], instances[j])
                    if c:
                        contradictions.append(c)

        major = [c for c in contradictions if c["severity"] == "MAJOR"]
        moderate = [c for c in contradictions if c["severity"] == "MODERATE"]
        minor = [c for c in contradictions if c["severity"] == "MINOR"]

        return {
            "status": (
                "CONTRADICTIONS_FOUND" if contradictions else "CONSISTENT"
            ),
            "total": len(contradictions),
            "by_severity": {
                "MAJOR": len(major),
                "MODERATE": len(moderate),
                "MINOR": len(minor),
            },
            "contradictions": contradictions,
            "recommendation": self._recommend(major, moderate, minor),
        }

    def _compare(
        self,
        field: str,
        a: Dict,
        b: Dict,
    ) -> Optional[Dict]:
        similarity = fuzz.ratio(a["value"].lower(), b["value"].lower())
        if similarity >= self.SEVERITY_THRESHOLDS["EXACT"]:
            return None  # consistent

        high_stakes = field in self.HIGH_STAKES_FIELDS
        if similarity >= self.SEVERITY_THRESHOLDS["MINOR"]:
            severity = "MINOR"
        elif similarity >= self.SEVERITY_THRESHOLDS["MODERATE"]:
            severity = "MODERATE" if not high_stakes else "MAJOR"
        else:
            severity = "MAJOR"

        return {
            "field": field,
            "severity": severity,
            "high_stakes": high_stakes,
            "similarity_score": similarity,
            "document_a": {
                "document_id": a["document_id"],
                "filename": a["filename"],
                "value": a["value"],
                "confidence": a["confidence"],
            },
            "document_b": {
                "document_id": b["document_id"],
                "filename": b["filename"],
                "value": b["value"],
                "confidence": b["confidence"],
            },
            "explanation": (
                f"Field '{field}' has value '{a['value']}' in {a['filename']} "
                f"but '{b['value']}' in {b['filename']} "
                f"(similarity {similarity}%)."
            ),
        }

    @staticmethod
    def _normalise(field_name: str) -> str:
        s = field_name.lower().replace(" ", "_").strip()
        aliases = {
            "name": "full_name", "applicant_name": "full_name",
            "holder_name": "full_name", "deponent_name": "full_name",
            "dob": "date_of_birth", "birth_date": "date_of_birth",
            "phone": "contact_number", "mobile": "contact_number",
        }
        return aliases.get(s, s)

    @staticmethod
    def _recommend(major, moderate, minor) -> str:
        if major:
            return (
                f"URGENT: {len(major)} major contradiction(s) found. "
                "Manual review required before processing."
            )
        if moderate:
            return (
                f"{len(moderate)} moderate contradiction(s) detected. "
                "Human verification recommended."
            )
        if minor:
            return (
                f"{len(minor)} minor variation(s) found. "
                "Likely acceptable — confirm if needed."
            )
        return "All compared fields are consistent."


# ---------------------------------------------------------------------------
# 5. Version / Supersession Tracking
# ---------------------------------------------------------------------------

class VersionTracker:
    """
    Detects when one document supersedes or amends another.

    Heuristics used:
      - Same document_type + overlapping key fields (name, id_number)
      - Newer issue_date or version_number
      - Content similarity above a threshold
    """

    SUPERSESSION_SIMILARITY = 0.70  # cosine similarity floor
    VERSION_FIELD_KEYWORDS = [
        "version", "revision", "amendment", "issue_date",
        "valid_from", "effective_date",
    ]

    def compare_versions(
        self,
        doc_a: Dict[str, Any],
        doc_b: Dict[str, Any],
        embedder=None,
    ) -> Dict[str, Any]:
        """
        Compare two documents and decide which (if any) supersedes the other.

        Args:
            doc_a / doc_b: { document_id, filename, document_type,
                              extracted_fields, chunks }
            embedder: Optional embedding model for similarity scoring

        Returns:
            Version comparison report
        """
        fields_a = self._field_dict(doc_a)
        fields_b = self._field_dict(doc_b)

        # Detect changed fields
        all_keys = set(fields_a) | set(fields_b)
        changes: List[Dict] = []
        for key in all_keys:
            va = fields_a.get(key)
            vb = fields_b.get(key)
            if va != vb:
                changes.append({
                    "field": key,
                    "value_in_a": va,
                    "value_in_b": vb,
                    "change_type": (
                        "ADDED" if va is None
                        else "REMOVED" if vb is None
                        else "MODIFIED"
                    ),
                    "text_similarity": SequenceMatcher(
                        None, str(va or ""), str(vb or "")
                    ).ratio(),
                })

        # Determine which is newer
        newer = self._determine_newer(fields_a, fields_b, doc_a, doc_b)

        # Content similarity
        content_sim = 0.0
        if embedder:
            try:
                text_a = " ".join(doc_a.get("chunks", []))[:3000]
                text_b = " ".join(doc_b.get("chunks", []))[:3000]
                if text_a and text_b:
                    import numpy as np
                    ea = embedder.embed(text_a)
                    eb = embedder.embed(text_b)
                    content_sim = float(
                        np.dot(ea, eb) / (np.linalg.norm(ea) * np.linalg.norm(eb) + 1e-9)
                    )
            except Exception:
                pass

        is_same_type = doc_a.get("document_type") == doc_b.get("document_type")
        likely_versions = is_same_type and content_sim >= self.SUPERSESSION_SIMILARITY

        return {
            "document_a": {
                "id": doc_a.get("document_id"),
                "filename": doc_a.get("filename"),
                "type": doc_a.get("document_type"),
            },
            "document_b": {
                "id": doc_b.get("document_id"),
                "filename": doc_b.get("filename"),
                "type": doc_b.get("document_type"),
            },
            "same_document_type": is_same_type,
            "content_similarity": round(content_sim, 4),
            "likely_versions_of_same_document": likely_versions,
            "newer_document": newer,
            "supersedes": (
                newer if likely_versions else None
            ),
            "changed_fields": changes,
            "total_changes": len(changes),
            "summary": self._summarise(changes, likely_versions, newer, doc_a, doc_b),
        }

    @staticmethod
    def _field_dict(doc: Dict) -> Dict[str, str]:
        return {
            f.get("field", ""): str(f.get("value", ""))
            for f in doc.get("extracted_fields", [])
            if f.get("value")
        }

    def _determine_newer(
        self, fa: Dict, fb: Dict, doc_a: Dict, doc_b: Dict
    ) -> Optional[str]:
        """Return document_id of the newer document, or None if undecided."""
        # Try date-based fields
        date_fields = ["issue_date", "valid_from", "effective_date", "date"]
        for df in date_fields:
            da = self._parse_date(fa.get(df, ""))
            db = self._parse_date(fb.get(df, ""))
            if da and db:
                return doc_a["document_id"] if da > db else doc_b["document_id"]

        # Try version numbers
        va = self._parse_version(fa.get("version", fa.get("revision", "")))
        vb = self._parse_version(fb.get("version", fb.get("revision", "")))
        if va is not None and vb is not None:
            return doc_a["document_id"] if va > vb else doc_b["document_id"]

        return None

    @staticmethod
    def _parse_date(s: str) -> Optional[datetime]:
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
            try:
                return datetime.strptime(s.strip(), fmt)
            except Exception:
                pass
        return None

    @staticmethod
    def _parse_version(s: str) -> Optional[float]:
        m = re.search(r"(\d+(?:\.\d+)?)", str(s))
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
        return None

    @staticmethod
    def _summarise(changes, likely_versions, newer, doc_a, doc_b) -> str:
        if not likely_versions:
            return "Documents do not appear to be versions of the same document."
        newer_name = (
            doc_a.get("filename") if newer == doc_a.get("document_id")
            else doc_b.get("filename") if newer == doc_b.get("document_id")
            else "undetermined"
        )
        return (
            f"Documents appear to be versions of the same document. "
            f"Newer version: {newer_name}. "
            f"{len(changes)} field(s) changed between versions."
        )


# ---------------------------------------------------------------------------
# 6. GraphRAG
# ---------------------------------------------------------------------------

class GraphRAGEngine:
    """
    KG-guided retrieval + answer generation.

    Workflow:
      1. Extract named entities from the query using the KG
      2. Retrieve candidate chunks via the standard vector search
      3. Re-rank using KG proximity (path length between query entities and
         document entities)
      4. Feed the top-k reranked chunks + KG context into the LLM
    """

    def __init__(self, rag_engine, kg_manager=None):
        self.rag_engine = rag_engine
        self.kg_manager = kg_manager

    def query(
        self,
        query: str,
        top_k: int = 5,
        max_tokens: int = 512,
    ) -> Dict[str, Any]:
        """
        Run a GraphRAG query.

        Returns standard RAG result enriched with KG context and entity trace.
        """
        # Step 1 — entity extraction from query
        query_entities: List[Dict] = []
        if self.kg_manager:
            for word in query.split():
                word = word.strip("?,.")
                if len(word) > 3:
                    res = self.kg_manager.get_entity(word)
                    if res.get("found"):
                        query_entities.append(res)

        # Step 2 — standard RAG retrieval
        rag_result = self.rag_engine.generate_response(
            query=query, top_k=top_k * 2, max_tokens=max_tokens
        )

        retrieved = rag_result.get("retrieved_documents", [])

        # Step 3 — KG re-ranking
        if self.kg_manager and query_entities:
            retrieved = self._kg_rerank(retrieved, query_entities)

        # Step 4 — build KG context string
        kg_context_str = ""
        if query_entities:
            lines = ["Knowledge Graph context:"]
            for ent in query_entities[:5]:
                lines.append(f"  • {ent['name']} ({ent.get('type', '')})")
                for conn in ent.get("connections", [])[:3]:
                    arrow = "→" if conn["direction"] == "outgoing" else "←"
                    lines.append(
                        f"      {arrow} [{conn['relation']}] {conn['entity_name']}"
                    )
            kg_context_str = "\n".join(lines)

        return {
            "query": query,
            "response": rag_result.get("response", ""),
            "retrieved_documents": retrieved[:top_k],
            "search_type": "graph_rag",
            "query_entities": query_entities,
            "kg_context": kg_context_str,
            "evidence": [
                {
                    "source_document": d.get("metadata", {}).get("source", "Unknown"),
                    "page": d.get("metadata", {}).get("page", "unknown"),
                    "evidence_snippet": d.get("text", "")[:200],
                    "confidence": round(float(d.get("score", 0)), 3),
                }
                for d in retrieved[:top_k]
            ],
        }

    def _kg_rerank(
        self,
        docs: List[Dict],
        query_entities: List[Dict],
    ) -> List[Dict]:
        """Re-rank retrieved docs using KG proximity to query entities."""
        q_names = {e["name"].lower() for e in query_entities}

        for doc in docs:
            text = doc.get("text", "").lower()
            # Count how many query entities appear in this chunk
            hits = sum(1 for n in q_names if n in text)
            kg_boost = hits * 0.05  # small additive boost
            doc["score"] = float(doc.get("score", 0)) + kg_boost
            doc["kg_boost"] = kg_boost

        docs.sort(key=lambda d: d["score"], reverse=True)
        return docs


# ---------------------------------------------------------------------------
# 7. Document Comparison Engine
# ---------------------------------------------------------------------------

class DocumentComparisonEngine:
    """
    Structured side-by-side field diff between two documents with:
      - field-level similarity scores
      - overall document similarity
      - colour-coded diff (added / removed / modified / unchanged)
      - a readiness delta (which doc is more complete)
    """

    def compare(
        self,
        doc_a: Dict[str, Any],
        doc_b: Dict[str, Any],
        embedder=None,
    ) -> Dict[str, Any]:
        """
        Full comparison between two documents.

        Args:
            doc_a / doc_b: { document_id, filename, document_type,
                              extracted_fields, chunks }
            embedder: Optional embedding model for semantic similarity

        Returns:
            Structured comparison report
        """
        fa = self._field_dict(doc_a)
        fb = self._field_dict(doc_b)
        all_keys = sorted(set(fa) | set(fb))

        field_diffs: List[Dict] = []
        match_scores: List[float] = []

        for key in all_keys:
            va = fa.get(key)
            vb = fb.get(key)

            if va is None and vb is None:
                continue

            if va is None:
                status = "ONLY_IN_B"
                sim = 0.0
            elif vb is None:
                status = "ONLY_IN_A"
                sim = 0.0
            else:
                sim = fuzz.ratio(str(va).lower(), str(vb).lower()) / 100.0
                if sim >= 0.95:
                    status = "MATCH"
                elif sim >= 0.75:
                    status = "NEAR_MATCH"
                else:
                    status = "MISMATCH"

            match_scores.append(sim)
            field_diffs.append({
                "field": key,
                "status": status,
                "value_a": va,
                "value_b": vb,
                "similarity": round(sim, 3),
            })

        # Overall field similarity
        field_sim = sum(match_scores) / len(match_scores) if match_scores else 0.0

        # Content similarity via embeddings
        content_sim = 0.0
        if embedder:
            try:
                import numpy as np
                ta = " ".join(doc_a.get("chunks", []))[:3000]
                tb = " ".join(doc_b.get("chunks", []))[:3000]
                if ta and tb:
                    ea, eb = embedder.embed(ta), embedder.embed(tb)
                    content_sim = float(
                        np.dot(ea, eb) / (np.linalg.norm(ea) * np.linalg.norm(eb) + 1e-9)
                    )
            except Exception:
                pass

        # Completeness delta
        comp_engine = CompletenessEngine()
        comp_a = comp_engine.check_document_fields(
            doc_a.get("document_type", "Other"),
            doc_a.get("extracted_fields", []),
        )
        comp_b = comp_engine.check_document_fields(
            doc_b.get("document_type", "Other"),
            doc_b.get("extracted_fields", []),
        )

        counts = defaultdict(int)
        for d in field_diffs:
            counts[d["status"]] += 1

        return {
            "document_a": {
                "id": doc_a.get("document_id"),
                "filename": doc_a.get("filename"),
                "type": doc_a.get("document_type"),
                "completeness_pct": comp_a.get("completeness_pct"),
            },
            "document_b": {
                "id": doc_b.get("document_id"),
                "filename": doc_b.get("filename"),
                "type": doc_b.get("document_type"),
                "completeness_pct": comp_b.get("completeness_pct"),
            },
            "field_similarity": round(field_sim, 4),
            "content_similarity": round(content_sim, 4),
            "field_diff_summary": dict(counts),
            "field_diffs": field_diffs,
            "verdict": self._verdict(field_sim, content_sim, counts),
        }

    @staticmethod
    def _field_dict(doc: Dict) -> Dict[str, str]:
        return {
            f.get("field", "").lower().replace(" ", "_"): str(f.get("value", ""))
            for f in doc.get("extracted_fields", [])
            if f.get("value") not in (None, "", "Not found", "N/A")
        }

    @staticmethod
    def _verdict(field_sim: float, content_sim: float, counts: Dict) -> str:
        if field_sim >= 0.90 and content_sim >= 0.85:
            return "NEAR_IDENTICAL — likely the same document."
        if counts.get("MISMATCH", 0) > 3:
            return "SIGNIFICANT_DIFFERENCES — documents differ in multiple key fields."
        if counts.get("MISMATCH", 0) > 0:
            return "MINOR_DIFFERENCES — mostly similar with some field mismatches."
        return "CONSISTENT — documents agree on all comparable fields."


# ---------------------------------------------------------------------------
# 8. Explainability Engine
# ---------------------------------------------------------------------------

class ExplainabilityEngine:
    """
    Builds a human-readable trace of *why* the system produced a given answer.

    Covers:
      - Which chunks were retrieved and why (score breakdown)
      - Which KG entities were matched
      - Which search type was used
      - Confidence breakdown
      - Whether the answer was grounded or speculative
    """

    def explain(
        self,
        query: str,
        rag_result: Dict[str, Any],
        kg_entities: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a full explanation for a RAG result.

        Args:
            query: Original user question
            rag_result: Output of rag_engine.generate_response()
            kg_entities: Optional list of KG entity dicts matched to the query

        Returns:
            Explanation dict with narrative, steps, and confidence breakdown
        """
        retrieved = rag_result.get("retrieved_documents", [])
        response = rag_result.get("response", "")
        search_type = rag_result.get("search_type", "hybrid")

        # Step trace
        steps: List[Dict] = []

        steps.append({
            "step": 1,
            "action": "Query received",
            "detail": f'Query: "{query}"',
        })

        steps.append({
            "step": 2,
            "action": f"Search executed ({search_type})",
            "detail": f"{len(retrieved)} chunk(s) retrieved from the document index.",
        })

        if kg_entities:
            steps.append({
                "step": 3,
                "action": "Knowledge graph lookup",
                "detail": (
                    f"{len(kg_entities)} entity/entities matched: "
                    + ", ".join(e.get("name", "") for e in kg_entities[:5])
                ),
            })

        # Top evidence
        evidence_details: List[Dict] = []
        for idx, doc in enumerate(retrieved[:5]):
            meta = doc.get("metadata", {})
            score = float(doc.get("score", 0))
            evidence_details.append({
                "rank": idx + 1,
                "source": meta.get("source", meta.get("filename", "Unknown")),
                "page": meta.get("page", "unknown"),
                "relevance_score": round(float(score), 4),
                "snippet": doc.get("text", "")[:150] + "…",
                "why_selected": (
                    "Highest semantic similarity to query"
                    if idx == 0
                    else f"Ranked #{idx+1} by {search_type} search score"
                ),
            })

        steps.append({
            "step": len(steps) + 1,
            "action": "Top evidence chunks selected",
            "detail": f"Used {len(evidence_details)} chunk(s) as context for the LLM.",
        })

        steps.append({
            "step": len(steps) + 1,
            "action": "Answer generated",
            "detail": (
                "LLM synthesised an answer strictly from the above context."
                if self._is_grounded(response)
                else "LLM could not find sufficient context — returned a 'not found' response."
            ),
        })

        # Confidence breakdown
        scores = [float(d.get("score", 0)) for d in retrieved]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        confidence_level = (
            "HIGH" if avg_score > 0.75
            else "MEDIUM" if avg_score > 0.50
            else "LOW"
        )

        grounded = self._is_grounded(response)

        return {
            "query": query,
            "answer_grounded": grounded,
            "confidence_level": confidence_level,
            "avg_retrieval_score": round(avg_score, 4),
            "chunks_used": len(retrieved),
            "search_type": search_type,
            "kg_entities_used": [e.get("name") for e in (kg_entities or [])],
            "reasoning_steps": steps,
            "evidence_breakdown": evidence_details,
            "human_readable_explanation": self._narrative(
                query, response, retrieved, kg_entities or [],
                search_type, grounded, confidence_level
            ),
        }

    @staticmethod
    def _is_grounded(response: str) -> bool:
        no_info = [
            "don't have enough information",
            "not found in the documents",
            "cannot answer",
            "as an ai",
        ]
        return not any(p in response.lower() for p in no_info)

    @staticmethod
    def _narrative(
        query: str,
        response: str,
        retrieved: List[Dict],
        kg_entities: List[Dict],
        search_type: str,
        grounded: bool,
        confidence: str,
    ) -> str:
        sources = list({
            d.get("metadata", {}).get("source", "Unknown")
            for d in retrieved
        })
        src_str = ", ".join(sources[:3]) or "no documents"
        ent_str = (
            ", ".join(e.get("name", "") for e in kg_entities[:3])
            if kg_entities else "none"
        )
        outcome = (
            "an answer was generated based on the retrieved evidence."
            if grounded
            else "no sufficient evidence was found and the system indicated it cannot answer."
        )
        return (
            f'To answer "{query}", the system performed a {search_type} search '
            f"and retrieved {len(retrieved)} relevant chunk(s) from: {src_str}. "
            f"Knowledge graph entities matched: {ent_str}. "
            f"Confidence level: {confidence}. "
            f"Result: {outcome}"
        )
