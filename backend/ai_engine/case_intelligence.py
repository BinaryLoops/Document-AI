"""
ai_engine/case_intelligence.py -- Case Intelligence module.

Detects:
  - Related cases (shared parties, references, facts)
  - Duplicate identities (same person across multiple documents)
  - Conflicting records (contradictory data across documents)

Uses cross-document linking via entity matching and text similarity.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from rapidfuzz import fuzz

from ai_engine.extractors import (
    extract_case_numbers,
    extract_dates,
    extract_people,
    ExtractedItem,
)

logger = logging.getLogger(__name__)


@dataclass
class RelatedCase:
    """A pair of documents linked by case relationship."""
    document_a: str
    document_b: str
    relationship: str          # "shared_party", "case_reference", "same_case", "related_facts"
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    shared_entities: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_a": self.document_a,
            "document_b": self.document_b,
            "relationship": self.relationship,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence[:5],
            "shared_entities": self.shared_entities,
        }


@dataclass
class DuplicateIdentity:
    """A person appearing across multiple documents with matching details."""
    name: str
    matching_names: List[str] = field(default_factory=list)
    document_refs: List[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    match_type: str = ""       # "exact", "fuzzy", "alias"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "matching_names": self.matching_names,
            "document_refs": self.document_refs,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence[:5],
            "match_type": self.match_type,
        }


@dataclass
class ConflictingRecord:
    """Contradictory data across documents."""
    field_name: str
    value_a: str
    value_b: str
    document_a: str
    document_b: str
    conflict_type: str         # "date_mismatch", "name_mismatch", "amount_mismatch"
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_name": self.field_name,
            "value_a": self.value_a,
            "value_b": self.value_b,
            "document_a": self.document_a,
            "document_b": self.document_b,
            "conflict_type": self.conflict_type,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence[:5],
        }


@dataclass
class CaseIntelligenceResult:
    """Complete case intelligence analysis."""
    related_cases: List[RelatedCase] = field(default_factory=list)
    duplicate_identities: List[DuplicateIdentity] = field(default_factory=list)
    conflicting_records: List[ConflictingRecord] = field(default_factory=list)
    risk_score: float = 0.0    # 0=clean, 1=high risk

    def to_dict(self) -> Dict[str, Any]:
        return {
            "related_cases": [r.to_dict() for r in self.related_cases],
            "duplicate_identities": [d.to_dict() for d in self.duplicate_identities],
            "conflicting_records": [c.to_dict() for c in self.conflicting_records],
            "risk_score": round(self.risk_score, 3),
            "summary": {
                "related_case_count": len(self.related_cases),
                "duplicate_identity_count": len(self.duplicate_identities),
                "conflict_count": len(self.conflicting_records),
            },
        }


class CaseIntelligence:
    """
    Cross-document intelligence for detecting related cases,
    duplicate identities, and conflicting records.

    Usage::

        intel = CaseIntelligence()
        result = intel.analyze([
            {"id": "doc1", "text": "...", "metadata": {...}},
            {"id": "doc2", "text": "...", "metadata": {...}},
        ])
    """

    # Fuzzy match threshold for names
    NAME_MATCH_THRESHOLD = 80

    def analyze(
        self,
        documents: List[Dict[str, Any]],
    ) -> CaseIntelligenceResult:
        """
        Analyze multiple documents for cross-document intelligence.

        Args:
            documents: List of dicts with keys: id, text, metadata (optional)

        Returns:
            CaseIntelligenceResult with findings.
        """
        result = CaseIntelligenceResult()

        if len(documents) < 2:
            logger.info("Need at least 2 documents for case intelligence")
            return result

        # Extract entities from each document
        doc_extractions: Dict[str, Dict] = {}
        for doc in documents:
            doc_id = doc.get("id", "")
            text = doc.get("text", "")
            doc_extractions[doc_id] = {
                "people": extract_people(text, doc_id),
                "case_numbers": extract_case_numbers(text, doc_id),
                "dates": extract_dates(text, doc_id),
                "text": text,
                "metadata": doc.get("metadata", {}),
            }

        # Detect related cases
        result.related_cases = self._find_related_cases(doc_extractions)

        # Detect duplicate identities
        result.duplicate_identities = self._find_duplicate_identities(doc_extractions)

        # Detect conflicting records
        result.conflicting_records = self._find_conflicts(doc_extractions)

        # Calculate risk score
        result.risk_score = self._calculate_risk(result)

        logger.info(
            "Case intelligence: %d related, %d duplicates, %d conflicts, risk=%.2f",
            len(result.related_cases),
            len(result.duplicate_identities),
            len(result.conflicting_records),
            result.risk_score,
        )

        return result

    def _find_related_cases(
        self, docs: Dict[str, Dict]
    ) -> List[RelatedCase]:
        """Find related cases across documents."""
        relations = []
        doc_ids = list(docs.keys())

        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                a_id, b_id = doc_ids[i], doc_ids[j]
                a, b = docs[a_id], docs[b_id]

                # Check shared case numbers
                a_cases = {item.value.upper() for item in a["case_numbers"]}
                b_cases = {item.value.upper() for item in b["case_numbers"]}
                shared_cases = a_cases & b_cases

                if shared_cases:
                    relations.append(RelatedCase(
                        document_a=a_id,
                        document_b=b_id,
                        relationship="same_case",
                        confidence=0.95,
                        evidence=[f"Shared case number: {c}" for c in shared_cases],
                        shared_entities=list(shared_cases),
                    ))
                    continue

                # Check shared people (fuzzy)
                a_names = [item.value for item in a["people"]]
                b_names = [item.value for item in b["people"]]
                shared = []

                for an in a_names:
                    for bn in b_names:
                        score = fuzz.ratio(an.lower(), bn.lower())
                        if score >= self.NAME_MATCH_THRESHOLD:
                            shared.append(an)
                            break

                if len(shared) >= 2:
                    relations.append(RelatedCase(
                        document_a=a_id,
                        document_b=b_id,
                        relationship="shared_party",
                        confidence=min(0.6 + len(shared) * 0.1, 0.95),
                        evidence=[f"Shared party: {n}" for n in shared],
                        shared_entities=shared,
                    ))

        return relations

    def _find_duplicate_identities(
        self, docs: Dict[str, Dict]
    ) -> List[DuplicateIdentity]:
        """Find same person appearing across multiple documents."""
        # Collect all names with their doc refs
        all_names: Dict[str, List[Tuple[str, str]]] = {}  # normalized_name -> [(doc_id, original_name)]

        for doc_id, data in docs.items():
            for person in data["people"]:
                name = person.value
                normalized = name.lower().strip()
                if normalized not in all_names:
                    all_names[normalized] = []
                all_names[normalized].append((doc_id, name))

        duplicates = []

        # Exact matches
        for norm_name, refs in all_names.items():
            if len(refs) >= 2:
                doc_ids = list(set(r[0] for r in refs))
                if len(doc_ids) >= 2:
                    duplicates.append(DuplicateIdentity(
                        name=refs[0][1],
                        matching_names=[r[1] for r in refs],
                        document_refs=doc_ids,
                        confidence=0.95,
                        evidence=[f"Name '{refs[0][1]}' found in {len(doc_ids)} documents"],
                        match_type="exact",
                    ))

        # Fuzzy matches between different normalized names
        norm_keys = list(all_names.keys())
        for i in range(len(norm_keys)):
            for j in range(i + 1, len(norm_keys)):
                score = fuzz.ratio(norm_keys[i], norm_keys[j])
                if score >= self.NAME_MATCH_THRESHOLD and score < 100:
                    a_refs = all_names[norm_keys[i]]
                    b_refs = all_names[norm_keys[j]]
                    a_docs = set(r[0] for r in a_refs)
                    b_docs = set(r[0] for r in b_refs)

                    if a_docs != b_docs:
                        duplicates.append(DuplicateIdentity(
                            name=a_refs[0][1],
                            matching_names=[a_refs[0][1], b_refs[0][1]],
                            document_refs=list(a_docs | b_docs),
                            confidence=score / 100,
                            evidence=[
                                f"Fuzzy match ({score}%): '{a_refs[0][1]}' ~ '{b_refs[0][1]}'"
                            ],
                            match_type="fuzzy",
                        ))

        return duplicates

    def _find_conflicts(
        self, docs: Dict[str, Dict]
    ) -> List[ConflictingRecord]:
        """Find conflicting data across documents for the same entity."""
        conflicts = []
        doc_ids = list(docs.keys())

        for i in range(len(doc_ids)):
            for j in range(i + 1, len(doc_ids)):
                a_id, b_id = doc_ids[i], doc_ids[j]
                a_meta = docs[a_id].get("metadata", {})
                b_meta = docs[b_id].get("metadata", {})

                # Check if docs are about the same person
                a_names = {item.value.lower() for item in docs[a_id]["people"]}
                b_names = {item.value.lower() for item in docs[b_id]["people"]}
                shared_names = a_names & b_names

                if not shared_names:
                    continue

                # Compare metadata fields
                for field_name in ["date_of_birth", "address", "father_name", "serial_number"]:
                    val_a = a_meta.get(field_name, "")
                    val_b = b_meta.get(field_name, "")
                    if val_a and val_b and val_a != val_b:
                        conflicts.append(ConflictingRecord(
                            field_name=field_name,
                            value_a=str(val_a),
                            value_b=str(val_b),
                            document_a=a_id,
                            document_b=b_id,
                            conflict_type=f"{field_name}_mismatch",
                            confidence=0.85,
                            evidence=[
                                f"Doc {a_id}: {field_name}='{val_a}'",
                                f"Doc {b_id}: {field_name}='{val_b}'",
                            ],
                        ))

        return conflicts

    def _calculate_risk(self, result: CaseIntelligenceResult) -> float:
        """Calculate overall risk score from findings."""
        score = 0.0
        score += len(result.conflicting_records) * 0.15
        score += len(result.duplicate_identities) * 0.05
        # Related cases are informational, not risky
        return min(score, 1.0)
