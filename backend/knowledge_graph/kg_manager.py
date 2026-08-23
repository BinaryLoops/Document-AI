"""
KGManager — singleton that owns the KG and persists it to kg_store.json.

Usage
-----
from knowledge_graph.kg_manager import kg_manager

kg_manager.process_extracted_fields(doc_id, filename, doc_type, fields, chunks)
kg_manager.process_document(chunks, metadata_list)   # regex fallback
kg_manager.get_entity("Ravi")
kg_manager.get_stats()
kg_manager.get_graph_data()
kg_manager.save()
kg_manager.clear()
"""

import json
import logging
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = Path(__file__).parent.parent / "kg_store.json"


class KGManager:
    """Manages the in-memory KG and handles disk persistence."""

    # ── Field name → entity type ─────────────────────────────────────────
    _FIELD_TYPE_MAP: Dict[str, str] = {
        "full_name":             "Person",
        "applicant_name":        "Person",
        "holder_name":           "Person",
        "deponent_name":         "Person",
        "father_name":           "Person",
        "mother_name":           "Person",
        "address":               "Location",
        "applicant_address":     "Location",
        "city":                  "Location",
        "state":                 "Location",
        "date_of_birth":         "Date",
        "issue_date":            "Date",
        "expiry_date":           "Date",
        "effective_date":        "Date",
        "valid_until":           "Date",
        "document_number":       "Identifier",
        "id_number":             "Identifier",
        "certificate_number":    "Identifier",
        "application_number":    "Identifier",
        "contact_number":        "ContactInfo",
        "email":                 "ContactInfo",
        "gender":                "Attribute",
        "nationality":           "Attribute",
        "document_type_specific":"DocumentType",
    }

    # ── Date field → specific relation label ─────────────────────────────
    _DATE_REL_MAP: Dict[str, str] = {
        "date_of_birth": "BORN_ON",
        "issue_date":    "ISSUED_ON",
        "expiry_date":   "VALID_UNTIL",
        "valid_until":   "VALID_UNTIL",
        "effective_date":"EFFECTIVE_FROM",
    }

    def __init__(self, store_path: Optional[str] = None):
        self.store_path = Path(
            store_path or os.getenv("KG_STORE_PATH", str(DEFAULT_STORE_PATH))
        )
        self._extractor = None  # lazy init

    # ─────────────────────────────────────────────────────────────────────
    # Init & properties
    # ─────────────────────────────────────────────────────────────────────

    def _init_extractor(self):
        if self._extractor is not None:
            return
        try:
            from knowledge_graph.extractor import KnowledgeGraphExtractor
            self._extractor = KnowledgeGraphExtractor()
            logger.info("KnowledgeGraphExtractor initialised")
            self._load()
        except Exception as e:
            logger.error(f"Failed to init KnowledgeGraphExtractor: {e}")
            raise

    @property
    def extractor(self):
        self._init_extractor()
        return self._extractor

    @property
    def kg(self):
        return self.extractor.kg

    # ─────────────────────────────────────────────────────────────────────
    # Primary build path — structured extracted fields
    # ─────────────────────────────────────────────────────────────────────

    def process_extracted_fields(
        self,
        document_id: str,
        filename: str,
        document_type: str,
        extracted_fields: List[Dict[str, Any]],
        chunks: Optional[List[str]] = None,
    ) -> None:
        """
        Build KG from structured field extractor output + optional raw chunks.
        This is the primary path — creates clean, typed entities.
        """
        try:
            self._init_extractor()
            ekg = self.kg

            # Document node
            doc_node_id = ekg.add_entity(
                name=filename, entity_type="Document", confidence=1.0,
                metadata={"document_id": document_id, "document_type": document_type},
            )

            field_node_ids: Dict[str, str] = {}

            for field in extracted_fields:
                fname  = field.get("field", "")
                fvalue = field.get("value")
                conf   = float(field.get("confidence", 0.5))

                if not fvalue or str(fvalue).lower() in (
                    "none", "null", "not found", "n/a", "",
                    "value not found in document"
                ):
                    continue

                etype = self._FIELD_TYPE_MAP.get(
                    fname.lower().replace(" ", "_"), "Attribute"
                )
                eid = ekg.add_entity(
                    str(fvalue), etype, conf,
                    metadata={"source_document": filename,
                              "document_id": document_id,
                              "field_name": fname},
                )
                field_node_ids[fname] = eid
                ekg.add_relation(eid, "EXTRACTED_FROM", doc_node_id, conf)

            # Also run regex on raw chunks to catch missed fields
            if chunks:
                regex_hits = self._regex_extract_fields(chunks)
                for fname, (etype, val) in regex_hits.items():
                    if fname in field_node_ids:
                        continue  # already from structured extractor
                    if any(val.lower() == str(f.get("value","")).lower()
                           for f in extracted_fields):
                        continue  # duplicate value
                    eid = ekg.add_entity(
                        val, etype, 0.8,
                        metadata={"source_document": filename,
                                  "field_name": fname},
                    )
                    field_node_ids[fname] = eid
                    ekg.add_relation(eid, "EXTRACTED_FROM", doc_node_id, 0.8)

            # Semantic edges
            person_id = (
                field_node_ids.get("full_name")
                or field_node_ids.get("applicant_name")
                or field_node_ids.get("holder_name")
                or field_node_ids.get("deponent_name")
            )

            if person_id:
                for df in ("date_of_birth", "issue_date", "expiry_date",
                           "valid_until", "effective_date"):
                    if df in field_node_ids:
                        rel = self._DATE_REL_MAP.get(df, "HAS_DATE")
                        ekg.add_relation(person_id, rel,
                                         field_node_ids[df], 0.95)

                for af in ("address", "applicant_address"):
                    if af in field_node_ids:
                        ekg.add_relation(person_id, "LIVES_AT",
                                         field_node_ids[af], 0.95)

                for idf in ("document_number", "id_number",
                            "certificate_number", "application_number"):
                    if idf in field_node_ids:
                        ekg.add_relation(person_id, "IDENTIFIED_BY",
                                         field_node_ids[idf], 0.95)

                for atf in ("gender",):
                    if atf in field_node_ids:
                        ekg.add_relation(person_id, "GENDER",
                                         field_node_ids[atf], 0.9)
                for atf in ("nationality",):
                    if atf in field_node_ids:
                        ekg.add_relation(person_id, "HAS_ATTRIBUTE",
                                         field_node_ids[atf], 0.9)

                # Org → ISSUED_TO → Person
                for eid in field_node_ids.values():
                    ent = ekg.entities.get(eid, {})
                    if ent.get("type") == "Organization":
                        ekg.add_relation(eid, "ISSUED_TO", person_id, 0.9)

            # Address PART_OF city/state
            for af in ("address", "applicant_address"):
                if af not in field_node_ids:
                    continue
                addr_val = str(next(
                    (f["value"] for f in extracted_fields
                     if f.get("field") == af and f.get("value")), ""
                ))
                parts = [p.strip() for p in addr_val.split(",")]
                for part in parts[1:]:
                    clean = re.sub(r'\d+', '', part).strip()
                    if clean and len(clean) > 2:
                        loc_id = ekg.add_entity(
                            clean, "Location", 0.8,
                            metadata={"source_document": filename,
                                      "field_name": "parsed_location"},
                        )
                        ekg.add_relation(field_node_ids[af], "PART_OF",
                                         loc_id, 0.85)

            self.save()
            logger.info(
                f"KG build done — entities={len(ekg.entities)}, "
                f"relations={len(ekg.relations)}"
            )
        except Exception as e:
            logger.warning(f"KG field processing failed (non-fatal): {e}")

    # ─────────────────────────────────────────────────────────────────────
    # Secondary build path — regex on raw text chunks
    # ─────────────────────────────────────────────────────────────────────

    def process_document(
        self,
        chunks: List[str],
        metadata_list: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Regex extraction on raw text chunks. Non-fatal fallback."""
        try:
            self._init_extractor()
            for i, chunk in enumerate(chunks):
                meta = (metadata_list[i]
                        if metadata_list and i < len(metadata_list) else {})
                filename = meta.get("source", meta.get("filename", "unknown"))
                self._extract_from_text(chunk, filename)
            self.save()
        except Exception as e:
            logger.warning(f"KG text extraction failed (non-fatal): {e}")

    def _regex_extract_fields(
        self, chunks: List[str]
    ) -> Dict[str, tuple]:
        """Return { field_name: (entity_type, value) } from regex scan."""
        text = " ".join(chunks)
        hits: Dict[str, tuple] = {}
        _patterns = {
            "full_name":      ("Person",     [
                r"Name\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})"
                r"(?=\s+(?:ID|id|S/O|Age|DOB|Date|Address|Gender|\d)|\s*$)"
            ]),
            "date_of_birth":  ("Date",       [
                r"Date\s+of\s+Birth\s*[:\-]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})"
            ]),
            "issue_date":     ("Date",       [
                r"Issue\s+Date\s*[:\-]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})"
            ]),
            "expiry_date":    ("Date",       [
                r"Valid\s+Until\s*[:\-]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})"
            ]),
            "document_number":("Identifier", [
                r"ID\s+Number\s*[:\-]\s*([A-Z0-9\-]{4,20})"
            ]),
            "address":        ("Location",   [
                r"Address\s*[:\-]\s*(.{10,80}?)"
                r"(?=\s*(?:Gender|Phone|Date|Issue|Valid|$))"
            ]),
            "gender":         ("Attribute",  [
                r"Gender\s*[:\-]\s*(Male|Female|Other)"
            ]),
        }
        for fname, (etype, pats) in _patterns.items():
            for pat in pats:
                m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
                if m:
                    val = m.group(1).strip()
                    if val and len(val) > 1:
                        hits[fname] = (etype, val)
                        break
        return hits

    def _extract_from_text(self, text: str, filename: str) -> None:
        """Full regex scan adding nodes directly to the KG."""
        ekg = self.kg

        patterns = {
            "Person": [
                r"Name\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})"
                r"(?=\s+(?:ID|id|S/O|Age|DOB|Date|Address|Gender|\d)|\s*$)",
            ],
            "Date": [
                r"(?:Date of Birth|DOB)\s*[:\-]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
                r"(?:Issue Date|Issued On)\s*[:\-]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
                r"(?:Valid Until|Expiry Date)\s*[:\-]\s*(\d{1,2}[-/]\d{1,2}[-/]\d{4})",
            ],
            "Identifier": [
                r"(?:ID Number|ID No)\s*[:\-]\s*([A-Z0-9\-]{6,20})",
                r"(?:Aadhaar)\s*[:\-]?\s*(\d{4}\s?\d{4}\s?\d{4})",
            ],
            "Location": [
                r"Address\s*[:\-]\s*(.{10,80}?)"
                r"(?=\s*(?:Gender|Phone|Date|Issue|Valid|City|State|$))",
            ],
            "Organization": [
                r"^(GOVERNMENT OF [A-Z\s]+)$",
                r"(?:Issued by|Issuing Authority)\s*[:\-]\s*(.{5,60})(?:\n|$)",
            ],
            "Attribute": [
                r"Gender\s*[:\-]\s*(Male|Female|Other)",
            ],
        }

        extracted: Dict[str, List[tuple]] = defaultdict(list)
        for etype, pat_list in patterns.items():
            for pat in pat_list:
                for m in re.finditer(pat, text, re.IGNORECASE | re.MULTILINE):
                    val = m.group(1).strip()
                    if val and len(val) > 1:
                        extracted[etype].append((val, pat))

        if not extracted:
            return

        doc_id = ekg.add_entity(filename, "Document", 1.0,
                                metadata={"source": filename})
        node_ids: Dict[str, str] = {}

        for etype, hits in extracted.items():
            for val, _ in hits:
                key = f"{etype}:{val}"
                if key not in node_ids:
                    eid = ekg.add_entity(val, etype, 0.85,
                                         metadata={"source_document": filename})
                    node_ids[key] = eid
                    ekg.add_relation(eid, "EXTRACTED_FROM", doc_id, 0.9)

        person_id = next(
            (node_ids[k] for k in node_ids if k.startswith("Person:")), None
        )
        if person_id:
            _date_rels = ["BORN_ON", "ISSUED_ON", "VALID_UNTIL"]
            _dc = 0
            for k, eid in node_ids.items():
                etype, _ = k.split(":", 1)
                if etype == "Date":
                    rel = _date_rels[_dc] if _dc < len(_date_rels) else "HAS_DATE"
                    ekg.add_relation(person_id, rel, eid, 0.9)
                    _dc += 1
                elif etype == "Location":
                    ekg.add_relation(person_id, "LIVES_AT", eid, 0.9)
                elif etype == "Identifier":
                    ekg.add_relation(person_id, "IDENTIFIED_BY", eid, 0.9)
                elif etype == "Attribute":
                    ekg.add_relation(person_id, "GENDER", eid, 0.9)
                elif etype == "Organization":
                    ekg.add_relation(eid, "ISSUED_TO", person_id, 0.9)

    # ─────────────────────────────────────────────────────────────────────
    # Query API
    # ─────────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        try:
            self._init_extractor()
            if not self.kg.entities and self.store_path.exists():
                self._load()

            entity_types: Dict[str, int] = {}
            for ent in self.kg.entities.values():
                t = ent.get("type", "Unknown")
                entity_types[t] = entity_types.get(t, 0) + 1

            relation_types: Dict[str, int] = {}
            for rel in self.kg.relations.values():
                t = rel.get("type", "Unknown")
                relation_types[t] = relation_types.get(t, 0) + 1

            return {
                "entity_count":   len(self.kg.entities),
                "relation_count": len(self.kg.relations),
                "entity_types":   entity_types,
                "relation_types": relation_types,
                "store_path":     str(self.store_path),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_graph_data(self, max_nodes: int = 100) -> Dict[str, Any]:
        try:
            self._init_extractor()
            if not self.kg.entities and self.store_path.exists():
                self._load()

            node_colors = {
                "Person":       "#818cf8",
                "Organization": "#f472b6",
                "Location":     "#34d399",
                "Date":         "#fbbf24",
                "Identifier":   "#60a5fa",
                "Concept":      "#60a5fa",
                "Attribute":    "#94a3b8",
                "Document":     "#475569",
                "Other":        "#6b7280",
            }

            entities  = self.kg.entities
            relations = self.kg.relations
            graph     = self.kg.graph

            if len(entities) > max_nodes:
                degree  = dict(graph.degree())
                top_ids = {
                    eid for eid, _ in
                    sorted(degree.items(), key=lambda x: x[1], reverse=True)[:max_nodes]
                }
            else:
                top_ids = set(entities.keys())

            nodes = [
                {
                    "id":    eid,
                    "name":  entities[eid].get("name", eid),
                    "type":  entities[eid].get("type", "Other"),
                    "color": node_colors.get(entities[eid].get("type","Other"),
                                             node_colors["Other"]),
                    "size":  5 + min(10, graph.degree(eid))
                             if graph.has_node(eid) else 5,
                }
                for eid in top_ids if eid in entities
            ]

            links = [
                {
                    "source": rel.get("source"),
                    "target": rel.get("target"),
                    "type":   rel.get("type", ""),
                    "value":  rel.get("confidence", 1.0),
                }
                for rel in relations.values()
                if rel.get("source") in top_ids and rel.get("target") in top_ids
            ]

            return {"nodes": nodes, "links": links}
        except Exception as e:
            logger.error(f"get_graph_data failed: {e}")
            return {"nodes": [], "links": [], "error": str(e)}

    def get_entity(self, name: str) -> Dict[str, Any]:
        """Case-insensitive partial entity lookup with connection details."""
        try:
            self._init_extractor()
            if not self.kg.entities and self.store_path.exists():
                self._load()

            name_lower = name.lower().strip()

            # Exact match first
            matched = [
                (eid, ent) for eid, ent in self.kg.entities.items()
                if ent.get("name", "").lower() == name_lower
            ]
            # Then partial match
            if not matched:
                matched = [
                    (eid, ent) for eid, ent in self.kg.entities.items()
                    if name_lower in ent.get("name", "").lower()
                ]

            if not matched:
                return {"found": False, "name": name}

            # Pick the cleanest match (shortest name = least noise)
            matched.sort(key=lambda x: len(x[1].get("name", "")))
            eid, ent = matched[0]

            # Build connections from the relations dict (not NetworkX graph)
            # so it works even if the graph edges weren't rebuilt
            connections = []
            for rel in self.kg.relations.values():
                src = rel.get("source")
                tgt = rel.get("target")
                if src == eid:
                    other = self.kg.entities.get(tgt, {})
                    connections.append({
                        "entity_name": other.get("name", tgt),
                        "entity_type": other.get("type", ""),
                        "relation":    rel.get("type", ""),
                        "direction":   "outgoing",
                    })
                elif tgt == eid:
                    other = self.kg.entities.get(src, {})
                    connections.append({
                        "entity_name": other.get("name", src),
                        "entity_type": other.get("type", ""),
                        "relation":    rel.get("type", ""),
                        "direction":   "incoming",
                    })

            return {
                "found":       True,
                "id":          eid,
                "name":        ent.get("name"),
                "type":        ent.get("type"),
                "confidence":  ent.get("confidence"),
                "connections": connections,
            }
        except Exception as e:
            return {"found": False, "error": str(e)}

    def build_from_rag(self, rag_engine, reset: bool = False) -> Dict[str, Any]:
        try:
            self._init_extractor()
            if reset:
                self._extractor.reset()

            vector_db = getattr(rag_engine, "vector_db", None)
            if vector_db is None or not hasattr(vector_db, "documents"):
                return {"status": "error",
                        "message": "RAG engine has no accessible vector_db.documents"}

            texts = []
            meta  = []
            for doc in vector_db.documents.values():
                texts.append(doc.text)
                meta.append(doc.metadata)

            if not texts:
                return {"status": "warning",
                        "message": "No documents in RAG engine to build from"}

            self._extractor.process_document_chunks(texts, meta)
            self.save()
            return {"status": "success",
                    "message": f"KG built from {len(texts)} chunks",
                    **self.get_stats()}
        except Exception as e:
            logger.error(f"build_from_rag failed: {e}")
            return {"status": "error", "message": str(e)}

    def clear(self) -> None:
        try:
            self._init_extractor()
            self._extractor.reset()
            if self.store_path.exists():
                self.store_path.unlink()
            logger.info("KG cleared")
        except Exception as e:
            logger.warning(f"KG clear failed: {e}")

    # ─────────────────────────────────────────────────────────────────────
    # Persistence
    # ─────────────────────────────────────────────────────────────────────

    def save(self) -> None:
        try:
            self._init_extractor()
            data = {
                "entities":           self.kg.entities,
                "relations":          self.kg.relations,
                "entity_frequencies": dict(self.kg.entity_frequencies),
                "relation_frequencies": dict(self.kg.relation_frequencies),
            }
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.store_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"KG save failed: {e}")

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            with open(self.store_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            kg = self.kg
            # Restore entities + NetworkX nodes
            for eid, ent in data.get("entities", {}).items():
                kg.entities[eid] = ent
                kg.graph.add_node(
                    eid,
                    name=ent.get("name", ""),
                    type=ent.get("type", ""),
                    confidence=ent.get("confidence", 1.0),
                )
            # Restore relations + NetworkX edges
            for rid, rel in data.get("relations", {}).items():
                kg.relations[rid] = rel
                src, tgt = rel.get("source"), rel.get("target")
                if src and tgt and src in kg.entities and tgt in kg.entities:
                    kg.graph.add_edge(
                        src, tgt,
                        key=rid,
                        type=rel.get("type", ""),
                        confidence=rel.get("confidence", 1.0),
                    )
            # Frequencies
            for eid, freq in data.get("entity_frequencies", {}).items():
                kg.entity_frequencies[eid] = freq
            for rid, freq in data.get("relation_frequencies", {}).items():
                kg.relation_frequencies[rid] = freq

            logger.info(
                f"KG loaded from {self.store_path} — "
                f"entities={len(kg.entities)}, relations={len(kg.relations)}"
            )
        except Exception as e:
            logger.warning(f"KG load failed (starting fresh): {e}")


# Shared singleton
kg_manager = KGManager()
