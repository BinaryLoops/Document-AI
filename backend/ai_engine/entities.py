"""
ai_engine/entities.py -- Government Entity Extraction module.

Generates entity profiles for:
  - Citizens (applicants, petitioners, respondents)
  - Officers (judges, inspectors, collectors, registrars)
  - Departments (ministries, directorates, boards)
  - Courts (high courts, district courts, tribunals)
  - Institutions (universities, schools, hospitals)

Each entity includes:
  - name, type, role
  - confidence, evidence (source snippet)
  - document references (which documents mention this entity)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ai_engine.extractors import (
    ExtractedItem,
    extract_organizations,
    extract_people,
)

logger = logging.getLogger(__name__)


class EntityType:
    CITIZEN = "citizen"
    OFFICER = "officer"
    DEPARTMENT = "department"
    COURT = "court"
    INSTITUTION = "institution"


_OFFICER_TITLES = {
    "judge", "magistrate", "justice", "inspector", "collector",
    "commissioner", "superintendent", "registrar", "director",
    "secretary", "tehsildar", "sdo", "bdo", "dsp", "sp", "ssp",
    "igs", "digs", "sub-inspector", "constable", "advocate",
    "prosecutor", "public prosecutor", "controller", "auditor",
    "minister", "governor", "president", "chairman", "chairperson",
}

_CITIZEN_ROLES = {
    "applicant", "petitioner", "respondent", "complainant",
    "accused", "plaintiff", "defendant", "witness", "deponent",
    "beneficiary", "licensee", "holder", "owner", "tenant",
    "buyer", "seller", "lessee", "lessor",
}

_COURT_KEYWORDS = {
    "supreme court", "high court", "district court", "sessions court",
    "magistrate court", "tribunal", "appellate", "bench",
    "lok adalat", "fast track court", "family court", "consumer court",
    "labour court", "nclt", "nclat", "itat", "cestat", "cat",
}

_INSTITUTION_KEYWORDS = {
    "university", "institute", "college", "school", "academy",
    "hospital", "polytechnic", "iit", "iim", "nit", "aiims",
}


@dataclass
class EntityProfile:
    """A recognized government entity with full profile."""
    entity_id: str = ""
    name: str = ""
    entity_type: str = ""        # citizen, officer, department, court, institution
    role: str = ""               # e.g. "petitioner", "judge", "issuing authority"
    confidence: float = 0.0
    evidence: List[str] = field(default_factory=list)
    document_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_type": self.entity_type,
            "role": self.role,
            "confidence": round(self.confidence, 3),
            "evidence": self.evidence[:5],
            "document_refs": self.document_refs,
            "metadata": self.metadata,
        }


class EntityExtractor:
    """
    Extract and classify government entities from document text.

    Produces structured entity profiles for citizens, officers,
    departments, courts, and institutions.
    """

    def extract(
        self,
        text: str,
        document_id: str = "",
        document_type: str = "",
        source: str = "",
    ) -> Dict[str, List[EntityProfile]]:
        """
        Extract all entity types from text.

        Returns:
            Dict with keys: citizens, officers, departments, courts, institutions
        """
        result = {
            "citizens": [],
            "officers": [],
            "departments": [],
            "courts": [],
            "institutions": [],
        }

        # Extract people and classify
        people = extract_people(text, source)
        for person in people:
            profile = self._classify_person(person, text, document_id)
            if profile.entity_type == EntityType.OFFICER:
                result["officers"].append(profile)
            else:
                result["citizens"].append(profile)

        # Extract organizations and classify
        orgs = extract_organizations(text, source)
        for org in orgs:
            profile = self._classify_org(org, text, document_id)
            if profile.entity_type == EntityType.COURT:
                result["courts"].append(profile)
            elif profile.entity_type == EntityType.INSTITUTION:
                result["institutions"].append(profile)
            else:
                result["departments"].append(profile)

        # Additional officer extraction by title
        title_officers = self._extract_titled_officers(text, document_id, source)
        existing_names = {o.name.lower() for o in result["officers"]}
        for officer in title_officers:
            if officer.name.lower() not in existing_names:
                result["officers"].append(officer)
                existing_names.add(officer.name.lower())

        logger.info(
            "Entities extracted: %d citizens, %d officers, %d departments, "
            "%d courts, %d institutions",
            len(result["citizens"]), len(result["officers"]),
            len(result["departments"]), len(result["courts"]),
            len(result["institutions"]),
        )

        return result

    def extract_flat(self, text: str, **kwargs) -> List[EntityProfile]:
        """Extract all entities as a flat list."""
        grouped = self.extract(text, **kwargs)
        flat = []
        for profiles in grouped.values():
            flat.extend(profiles)
        return flat

    # ── Classification ───────────────────────────────────────────────────

    def _classify_person(
        self, item: ExtractedItem, text: str, doc_id: str
    ) -> EntityProfile:
        """Classify a person as citizen or officer."""
        name = item.value
        context = item.evidence.lower()

        # Check for officer titles
        is_officer = False
        role = ""
        for title in _OFFICER_TITLES:
            if title in context:
                is_officer = True
                role = title.title()
                break

        if not is_officer:
            # Check citizen roles
            for cr in _CITIZEN_ROLES:
                if cr in context:
                    role = cr.title()
                    break

        return EntityProfile(
            entity_id=f"{'off' if is_officer else 'cit'}_{hash(name) % 100000:05d}",
            name=name,
            entity_type=EntityType.OFFICER if is_officer else EntityType.CITIZEN,
            role=role,
            confidence=item.confidence,
            evidence=[item.evidence],
            document_refs=[doc_id] if doc_id else [],
        )

    def _classify_org(
        self, item: ExtractedItem, text: str, doc_id: str
    ) -> EntityProfile:
        """Classify an organization as department, court, or institution."""
        name = item.value
        name_lower = name.lower()

        # Check court
        for kw in _COURT_KEYWORDS:
            if kw in name_lower:
                return EntityProfile(
                    entity_id=f"court_{hash(name) % 100000:05d}",
                    name=name,
                    entity_type=EntityType.COURT,
                    role="court",
                    confidence=item.confidence,
                    evidence=[item.evidence],
                    document_refs=[doc_id] if doc_id else [],
                )

        # Check institution
        for kw in _INSTITUTION_KEYWORDS:
            if kw in name_lower:
                return EntityProfile(
                    entity_id=f"inst_{hash(name) % 100000:05d}",
                    name=name,
                    entity_type=EntityType.INSTITUTION,
                    role="institution",
                    confidence=item.confidence,
                    evidence=[item.evidence],
                    document_refs=[doc_id] if doc_id else [],
                )

        # Default: department
        return EntityProfile(
            entity_id=f"dept_{hash(name) % 100000:05d}",
            name=name,
            entity_type=EntityType.DEPARTMENT,
            role="government department",
            confidence=item.confidence,
            evidence=[item.evidence],
            document_refs=[doc_id] if doc_id else [],
        )

    def _extract_titled_officers(
        self, text: str, doc_id: str, source: str
    ) -> List[EntityProfile]:
        """Extract officers by their title patterns (Shri X, Justice Y)."""
        officers = []
        seen: Set[str] = set()

        title_pattern = r'\b((?:Shri|Smt|Dr\.|Mr\.|Mrs\.|Ms\.|Justice|Hon\'?ble|Adv\.?)\s+[A-Z][a-zA-Z\.\s]{2,30})'
        for match in re.finditer(title_pattern, text):
            name = match.group(1).strip().rstrip(".,;:")
            if name.lower() in seen or len(name) < 5:
                continue
            seen.add(name.lower())

            start = max(0, match.start() - 30)
            end = min(len(text), match.end() + 30)
            context = text[start:end].strip()

            # Determine role from title
            role = "Official"
            name_lower = name.lower()
            if "justice" in name_lower or "hon" in name_lower:
                role = "Judge"
            elif "dr." in name_lower:
                role = "Doctor/Official"

            officers.append(EntityProfile(
                entity_id=f"off_{hash(name) % 100000:05d}",
                name=name,
                entity_type=EntityType.OFFICER,
                role=role,
                confidence=0.80,
                evidence=[context],
                document_refs=[doc_id] if doc_id else [],
            ))

        return officers
