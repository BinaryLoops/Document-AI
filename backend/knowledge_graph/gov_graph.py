"""
knowledge_graph/gov_graph.py -- Government Knowledge Graph Layer.

Extends the existing KnowledgeGraph with government-specific node types,
relationship types, and analysis features.

Node Types:
  - Citizen, Officer, Department, Document, Case, Location, Institution

Relationship Types:
  - owns, issued_by, verified_by, belongs_to, linked_case, handled_by

Features:
  - Cross-document linking
  - Fraud cluster detection
  - Duplicate identity detection
  - Timeline graph
  - Department graph
  - Visual export (JSON for D3.js)
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
from rapidfuzz import fuzz

from knowledge_graph.model import Entity, KnowledgeGraph, Relation

logger = logging.getLogger(__name__)


# ── Node types ───────────────────────────────────────────────────────────────

class NodeType:
    CITIZEN = "Citizen"
    OFFICER = "Officer"
    DEPARTMENT = "Department"
    DOCUMENT = "Document"
    CASE = "Case"
    LOCATION = "Location"
    INSTITUTION = "Institution"

    ALL = [CITIZEN, OFFICER, DEPARTMENT, DOCUMENT, CASE, LOCATION, INSTITUTION]


# ── Relationship types ───────────────────────────────────────────────────────

class RelType:
    OWNS = "owns"                   # Citizen -> Document
    ISSUED_BY = "issued_by"         # Document -> Department/Officer
    VERIFIED_BY = "verified_by"     # Document -> Officer
    BELONGS_TO = "belongs_to"       # Officer -> Department, Location -> Location
    LINKED_CASE = "linked_case"     # Case -> Case, Document -> Case
    HANDLED_BY = "handled_by"       # Case -> Officer, Document -> Officer

    ALL = [OWNS, ISSUED_BY, VERIFIED_BY, BELONGS_TO, LINKED_CASE, HANDLED_BY]


# ── Node color map for visualization ────────────────────────────────────────

NODE_COLORS = {
    NodeType.CITIZEN:     "#4CAF50",   # Green
    NodeType.OFFICER:     "#2196F3",   # Blue
    NodeType.DEPARTMENT:  "#FF9800",   # Orange
    NodeType.DOCUMENT:    "#9C27B0",   # Purple
    NodeType.CASE:        "#F44336",   # Red
    NodeType.LOCATION:    "#00BCD4",   # Cyan
    NodeType.INSTITUTION: "#795548",   # Brown
}


# ── Government Knowledge Graph ──────────────────────────────────────────────

class GovernmentKnowledgeGraph:
    """
    Government-specific knowledge graph built on top of the existing
    KnowledgeGraph module.

    Provides:
      - Typed node management (Citizen, Officer, Document, etc.)
      - Government relationship types
      - Cross-document entity linking
      - Fraud cluster detection
      - Duplicate identity detection
      - Timeline and department graph views
      - Visual export for D3.js
    """

    def __init__(self, base_kg: Optional[KnowledgeGraph] = None):
        self.kg = base_kg or KnowledgeGraph()
        # Type indices for fast lookup
        self._type_index: Dict[str, Set[str]] = defaultdict(set)  # type -> set of entity IDs
        self._name_index: Dict[str, Set[str]] = defaultdict(set)  # normalized_name -> entity IDs
        self._doc_index: Dict[str, str] = {}   # document_id -> entity_id in graph

    # ── Node Management ──────────────────────────────────────────────────

    def add_citizen(
        self, name: str, metadata: Optional[Dict] = None, **kwargs
    ) -> str:
        return self._add_node(name, NodeType.CITIZEN, metadata, **kwargs)

    def add_officer(
        self, name: str, metadata: Optional[Dict] = None, **kwargs
    ) -> str:
        return self._add_node(name, NodeType.OFFICER, metadata, **kwargs)

    def add_department(
        self, name: str, metadata: Optional[Dict] = None, **kwargs
    ) -> str:
        return self._add_node(name, NodeType.DEPARTMENT, metadata, **kwargs)

    def add_document(
        self, doc_id: str, name: str, metadata: Optional[Dict] = None, **kwargs
    ) -> str:
        eid = self._add_node(name, NodeType.DOCUMENT, {
            **(metadata or {}), "document_id": doc_id
        }, **kwargs)
        self._doc_index[doc_id] = eid
        return eid

    def add_case(
        self, case_number: str, metadata: Optional[Dict] = None, **kwargs
    ) -> str:
        return self._add_node(case_number, NodeType.CASE, metadata, **kwargs)

    def add_location(
        self, name: str, metadata: Optional[Dict] = None, **kwargs
    ) -> str:
        return self._add_node(name, NodeType.LOCATION, metadata, **kwargs)

    def add_institution(
        self, name: str, metadata: Optional[Dict] = None, **kwargs
    ) -> str:
        return self._add_node(name, NodeType.INSTITUTION, metadata, **kwargs)

    def _add_node(
        self, name: str, node_type: str, metadata: Optional[Dict] = None,
        entity_id: Optional[str] = None,
    ) -> str:
        """Add a typed node, deduplicating by name+type."""
        # Check existing
        existing = self.kg.get_entity_by_name(name, node_type)
        if existing:
            eid = existing[0].id
            # Merge metadata
            if metadata:
                existing[0].metadata.update(metadata)
            return eid

        entity = Entity(
            name=name,
            type=node_type,
            metadata=metadata or {},
            id=entity_id or str(uuid.uuid4()),
        )
        eid = self.kg.add_entity(entity)
        self._type_index[node_type].add(eid)
        self._name_index[name.lower().strip()].add(eid)
        return eid

    # ── Relationship Management ──────────────────────────────────────────

    def add_owns(self, citizen_id: str, document_id: str, **meta) -> str:
        return self._add_rel(citizen_id, document_id, RelType.OWNS, **meta)

    def add_issued_by(self, document_id: str, issuer_id: str, **meta) -> str:
        return self._add_rel(document_id, issuer_id, RelType.ISSUED_BY, **meta)

    def add_verified_by(self, document_id: str, officer_id: str, **meta) -> str:
        return self._add_rel(document_id, officer_id, RelType.VERIFIED_BY, **meta)

    def add_belongs_to(self, child_id: str, parent_id: str, **meta) -> str:
        return self._add_rel(child_id, parent_id, RelType.BELONGS_TO, **meta)

    def add_linked_case(self, entity_id: str, case_id: str, **meta) -> str:
        return self._add_rel(entity_id, case_id, RelType.LINKED_CASE, **meta)

    def add_handled_by(self, entity_id: str, officer_id: str, **meta) -> str:
        return self._add_rel(entity_id, officer_id, RelType.HANDLED_BY, **meta)

    def _add_rel(
        self, source: str, target: str, rel_type: str, weight: float = 1.0, **meta
    ) -> str:
        rel = Relation(
            source=source, target=target,
            type=rel_type, weight=weight,
            metadata=meta,
        )
        return self.kg.add_relation(rel)

    # ── Queries ──────────────────────────────────────────────────────────

    def get_node(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get a node by ID with full details."""
        entity = self.kg.get_entity(entity_id)
        if not entity:
            return None
        neighbors = self.kg.get_neighbors(entity_id)
        # Also get incoming edges
        incoming = []
        for eid, e in self.kg.entities.items():
            if eid == entity_id:
                continue
            for n_ent, n_rel in self.kg.get_neighbors(eid):
                if n_ent.id == entity_id:
                    incoming.append({
                        "entity_id": eid,
                        "entity_name": e.name,
                        "entity_type": e.type,
                        "relationship": n_rel.type,
                    })

        return {
            "entity_id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "metadata": entity.metadata,
            "outgoing": [
                {
                    "entity_id": n.id,
                    "entity_name": n.name,
                    "entity_type": n.type,
                    "relationship": r.type,
                    "weight": r.weight,
                }
                for n, r in neighbors
            ],
            "incoming": incoming,
        }

    def get_nodes_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        """Get all nodes of a specific type."""
        results = []
        for eid in self._type_index.get(node_type, set()):
            entity = self.kg.get_entity(eid)
            if entity:
                results.append({
                    "entity_id": entity.id,
                    "name": entity.name,
                    "type": entity.type,
                    "metadata": entity.metadata,
                })
        return results

    def get_document_graph(self, document_id: str) -> Dict[str, Any]:
        """Get the full subgraph around a document."""
        eid = self._doc_index.get(document_id)
        if not eid:
            # Try finding by metadata
            for entity in self.kg.entities.values():
                if entity.metadata.get("document_id") == document_id:
                    eid = entity.id
                    break
        if not eid:
            return {"error": "Document not found in graph", "nodes": [], "edges": []}
        return self._subgraph(eid, depth=2)

    def get_citizen_graph(self, citizen_id: str) -> Dict[str, Any]:
        """Get the full subgraph around a citizen."""
        return self._subgraph(citizen_id, depth=2)

    def get_case_graph(self, case_id: str) -> Dict[str, Any]:
        """Get the full subgraph around a case."""
        # Try to find by case number
        entities = self.kg.get_entity_by_name(case_id, NodeType.CASE)
        if entities:
            return self._subgraph(entities[0].id, depth=2)
        return self._subgraph(case_id, depth=2)

    def get_officer_graph(self, officer_id: str) -> Dict[str, Any]:
        """Get the full subgraph around an officer."""
        return self._subgraph(officer_id, depth=2)

    def _subgraph(self, center_id: str, depth: int = 2) -> Dict[str, Any]:
        """Extract a subgraph around a center node up to N hops."""
        entity = self.kg.get_entity(center_id)
        if not entity:
            return {"error": "Entity not found", "nodes": [], "edges": []}

        visited: Set[str] = set()
        nodes: List[Dict] = []
        edges: List[Dict] = []
        queue = [(center_id, 0)]

        while queue:
            current, d = queue.pop(0)
            if current in visited or d > depth:
                continue
            visited.add(current)

            e = self.kg.get_entity(current)
            if e:
                nodes.append({
                    "id": e.id,
                    "name": e.name,
                    "type": e.type,
                    "color": NODE_COLORS.get(e.type, "#999"),
                    "metadata": e.metadata,
                    "is_center": current == center_id,
                })

            # Outgoing
            for neighbor, rel in self.kg.get_neighbors(current):
                edges.append({
                    "source": current,
                    "target": neighbor.id,
                    "type": rel.type,
                    "weight": rel.weight,
                })
                if neighbor.id not in visited:
                    queue.append((neighbor.id, d + 1))

            # Incoming (reverse)
            for eid, ent in self.kg.entities.items():
                if eid in visited:
                    continue
                for n_ent, n_rel in self.kg.get_neighbors(eid):
                    if n_ent.id == current:
                        edges.append({
                            "source": eid,
                            "target": current,
                            "type": n_rel.type,
                            "weight": n_rel.weight,
                        })
                        if eid not in visited:
                            queue.append((eid, d + 1))

        return {
            "center": {"id": center_id, "name": entity.name, "type": entity.type},
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    # ── Fraud Cluster Detection ──────────────────────────────────────────

    def detect_fraud_clusters(self, min_cluster_size: int = 3) -> List[Dict[str, Any]]:
        """
        Detect fraud clusters — tightly connected subgraphs of entities
        that share documents, cases, or identities in suspicious patterns.
        """
        clusters = []

        # Use NetworkX connected components on the undirected view
        undirected = self.kg.graph.to_undirected()
        components = list(nx.connected_components(undirected))

        for comp in components:
            if len(comp) < min_cluster_size:
                continue

            # Analyze cluster composition
            type_counts = defaultdict(int)
            entities_in_cluster = []
            for eid in comp:
                e = self.kg.get_entity(eid)
                if e:
                    type_counts[e.type] += 1
                    entities_in_cluster.append({
                        "id": e.id, "name": e.name, "type": e.type,
                    })

            # Fraud indicators
            risk_score = 0.0
            indicators = []

            # Many documents for a single citizen
            if type_counts.get(NodeType.CITIZEN, 0) == 1 and type_counts.get(NodeType.DOCUMENT, 0) >= 5:
                risk_score += 0.3
                indicators.append("Single citizen with many documents")

            # Multiple cases linked to same person
            if type_counts.get(NodeType.CASE, 0) >= 3:
                risk_score += 0.2
                indicators.append("Multiple cases in cluster")

            # Cross-department documents
            if type_counts.get(NodeType.DEPARTMENT, 0) >= 3:
                risk_score += 0.1
                indicators.append("Cross-department connections")

            # Dense cluster (many edges per node)
            subgraph = self.kg.graph.subgraph(comp)
            density = nx.density(subgraph)
            if density > 0.5:
                risk_score += 0.2
                indicators.append(f"Dense cluster (density={density:.2f})")

            risk_score = min(risk_score, 1.0)

            if risk_score > 0.1:
                clusters.append({
                    "cluster_id": str(uuid.uuid4())[:8],
                    "size": len(comp),
                    "risk_score": round(risk_score, 3),
                    "indicators": indicators,
                    "type_distribution": dict(type_counts),
                    "entities": entities_in_cluster[:20],
                    "density": round(density, 3),
                })

        clusters.sort(key=lambda c: c["risk_score"], reverse=True)
        logger.info("Detected %d fraud clusters", len(clusters))
        return clusters

    # ── Duplicate Identity Detection ─────────────────────────────────────

    def detect_duplicate_identities(
        self, threshold: int = 80
    ) -> List[Dict[str, Any]]:
        """
        Detect potential duplicate identities — same person with slightly
        different names across documents.
        """
        duplicates = []
        citizens = self.get_nodes_by_type(NodeType.CITIZEN)

        for i in range(len(citizens)):
            for j in range(i + 1, len(citizens)):
                a = citizens[i]
                b = citizens[j]
                score = fuzz.ratio(a["name"].lower(), b["name"].lower())

                if score >= threshold and score < 100:
                    duplicates.append({
                        "identity_a": {
                            "id": a["entity_id"],
                            "name": a["name"],
                        },
                        "identity_b": {
                            "id": b["entity_id"],
                            "name": b["name"],
                        },
                        "match_score": score / 100,
                        "match_type": "fuzzy",
                        "recommendation": "merge" if score >= 90 else "review",
                    })

        duplicates.sort(key=lambda d: d["match_score"], reverse=True)
        return duplicates

    # ── Timeline Graph ───────────────────────────────────────────────────

    def get_timeline_graph(self, entity_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Build a timeline graph of events connected to an entity or all entities.
        Nodes are events/documents sorted by date.
        """
        events = []

        target_entities = (
            {entity_id} if entity_id else set(self.kg.entities.keys())
        )

        for eid in target_entities:
            entity = self.kg.get_entity(eid)
            if not entity:
                continue

            date_fields = ["issue_date", "date_of_birth", "effective_date",
                           "upload_timestamp", "created_at", "filing_date"]

            for df in date_fields:
                date_val = entity.metadata.get(df)
                if date_val:
                    events.append({
                        "date": str(date_val),
                        "event": f"{entity.name} ({entity.type})",
                        "event_type": df.replace("_", " ").title(),
                        "entity_id": entity.id,
                        "entity_type": entity.type,
                    })

        # Sort chronologically
        events.sort(key=lambda e: e["date"])

        return {
            "events": events,
            "event_count": len(events),
        }

    # ── Department Graph ─────────────────────────────────────────────────

    def get_department_graph(self) -> Dict[str, Any]:
        """
        Build department-centric graph showing:
        - Departments and their officers
        - Documents issued by each department
        - Cases handled by each department
        """
        departments = self.get_nodes_by_type(NodeType.DEPARTMENT)
        dept_data = []

        for dept in departments:
            dept_id = dept["entity_id"]
            neighbors = self.kg.get_neighbors(dept_id)

            # Incoming edges: documents issued_by, officers belongs_to
            officers = []
            documents = []
            cases = []

            for eid, e in self.kg.entities.items():
                for n_ent, n_rel in self.kg.get_neighbors(eid):
                    if n_ent.id == dept_id:
                        if e.type == NodeType.OFFICER and n_rel.type == RelType.BELONGS_TO:
                            officers.append({"id": e.id, "name": e.name})
                        elif e.type == NodeType.DOCUMENT and n_rel.type == RelType.ISSUED_BY:
                            documents.append({"id": e.id, "name": e.name})

            # Outgoing neighbors
            for n_ent, n_rel in neighbors:
                if n_ent.type == NodeType.CASE:
                    cases.append({"id": n_ent.id, "name": n_ent.name})

            dept_data.append({
                "department": dept,
                "officers": officers,
                "documents": documents,
                "cases": cases,
                "stats": {
                    "officer_count": len(officers),
                    "document_count": len(documents),
                    "case_count": len(cases),
                },
            })

        return {
            "departments": dept_data,
            "total_departments": len(dept_data),
        }

    # ── Visual Export ────────────────────────────────────────────────────

    def export_graph_data(self) -> Dict[str, Any]:
        """
        Export the full graph as D3.js-compatible JSON.
        Nodes include color by type. Edges include type labels.
        """
        nodes = []
        for eid, entity in self.kg.entities.items():
            nodes.append({
                "id": entity.id,
                "name": entity.name,
                "type": entity.type,
                "color": NODE_COLORS.get(entity.type, "#999"),
                "metadata": entity.metadata,
            })

        edges = []
        for rid, rel in self.kg.relations.items():
            edges.append({
                "source": rel.source,
                "target": rel.target,
                "type": rel.type,
                "weight": rel.weight,
                "label": rel.type.replace("_", " "),
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "node_types": {nt: len(ids) for nt, ids in self._type_index.items()},
        }

    # ── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Get graph statistics."""
        type_counts = {nt: len(ids) for nt, ids in self._type_index.items()}
        rel_type_counts = defaultdict(int)
        for rel in self.kg.relations.values():
            rel_type_counts[rel.type] += 1

        return {
            "total_nodes": len(self.kg.entities),
            "total_edges": len(self.kg.relations),
            "node_types": dict(type_counts),
            "relationship_types": dict(rel_type_counts),
            "density": round(nx.density(self.kg.graph), 4) if self.kg.entities else 0,
            "connected_components": nx.number_weakly_connected_components(self.kg.graph) if self.kg.entities else 0,
        }

    # ── Bulk Ingest from AI Engine ───────────────────────────────────────

    def ingest_document_entities(
        self,
        document_id: str,
        document_name: str,
        document_type: str = "",
        owner: str = "",
        entities: Optional[Dict[str, List]] = None,
        metadata: Optional[Dict] = None,
    ) -> Dict[str, int]:
        """
        Ingest extracted entities from the AI engine into the graph.

        Args:
            document_id: Document ID
            document_name: Display name
            document_type: Type (passport, fir, etc.)
            owner: Owner/citizen name
            entities: Dict from EntityExtractor.extract() with keys:
                      citizens, officers, departments, courts, institutions
            metadata: Document metadata

        Returns:
            Counts of nodes and edges created.
        """
        counts = {"nodes": 0, "edges": 0}
        ents = entities or {}
        meta = metadata or {}

        # Add document node
        doc_eid = self.add_document(
            document_id, document_name,
            {"document_type": document_type, **(meta)},
        )
        counts["nodes"] += 1

        # Add owner/citizen
        if owner:
            citizen_eid = self.add_citizen(owner)
            self.add_owns(citizen_eid, doc_eid)
            counts["nodes"] += 1
            counts["edges"] += 1

        # Citizens from entities
        for citizen in ents.get("citizens", []):
            name = citizen.name if hasattr(citizen, "name") else citizen.get("name", "")
            if name:
                c_eid = self.add_citizen(name)
                counts["nodes"] += 1

        # Officers
        for officer in ents.get("officers", []):
            name = officer.name if hasattr(officer, "name") else officer.get("name", "")
            if name:
                o_eid = self.add_officer(name, {"role": getattr(officer, "role", "")})
                self.add_handled_by(doc_eid, o_eid)
                counts["nodes"] += 1
                counts["edges"] += 1

        # Departments
        for dept in ents.get("departments", []):
            name = dept.name if hasattr(dept, "name") else dept.get("name", "")
            if name:
                d_eid = self.add_department(name)
                self.add_issued_by(doc_eid, d_eid)
                counts["nodes"] += 1
                counts["edges"] += 1

        # Courts
        for court in ents.get("courts", []):
            name = court.name if hasattr(court, "name") else court.get("name", "")
            if name:
                i_eid = self.add_institution(name, {"sub_type": "court"})
                counts["nodes"] += 1

        # Institutions
        for inst in ents.get("institutions", []):
            name = inst.name if hasattr(inst, "name") else inst.get("name", "")
            if name:
                i_eid = self.add_institution(name)
                counts["nodes"] += 1

        logger.info(
            "Ingested document %s: +%d nodes, +%d edges",
            document_id, counts["nodes"], counts["edges"],
        )
        return counts
