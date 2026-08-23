"""
knowledge_graph/gov_routes.py -- FastAPI endpoints for the Government Knowledge Graph.

Endpoints:
  GET  /graph/document/{id}   — Document subgraph
  GET  /graph/citizen/{id}    — Citizen subgraph
  GET  /graph/case/{id}       — Case subgraph
  GET  /graph/officer/{id}    — Officer subgraph
  GET  /graph/stats           — Graph statistics
  GET  /graph/export          — Full graph D3.js export
  GET  /graph/departments     — Department graph
  GET  /graph/timeline        — Timeline graph
  GET  /graph/fraud-clusters  — Fraud cluster detection
  GET  /graph/duplicates      — Duplicate identity detection
  POST /graph/ingest          — Ingest document entities into graph
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from knowledge_graph.gov_graph import GovernmentKnowledgeGraph

logger = logging.getLogger(__name__)


# ── Request models ───────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    document_id: str = Field(..., description="Document ID")
    document_name: str = Field(..., description="Display name for the document")
    document_type: str = Field("", description="Document category (passport, fir, etc.)")
    owner: str = Field("", description="Owner / citizen name")
    citizens: List[Dict[str, Any]] = Field(default_factory=list)
    officers: List[Dict[str, Any]] = Field(default_factory=list)
    departments: List[Dict[str, Any]] = Field(default_factory=list)
    courts: List[Dict[str, Any]] = Field(default_factory=list)
    institutions: List[Dict[str, Any]] = Field(default_factory=list)
    cases: List[Dict[str, Any]] = Field(default_factory=list)
    locations: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ── Router factory ───────────────────────────────────────────────────────────

def create_graph_router(gov_kg: GovernmentKnowledgeGraph) -> APIRouter:
    """Create and return the Government Knowledge Graph API router."""

    router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])

    # ── GET /graph/document/{id} ─────────────────────────────────────────

    @router.get(
        "/document/{document_id}",
        summary="Get document subgraph",
    )
    async def get_document_graph(document_id: str) -> Dict[str, Any]:
        """
        Get the full subgraph around a document (2 hops).

        Returns all connected entities: owner, issuing department,
        verifying officers, linked cases, etc.
        """
        result = gov_kg.get_document_graph(document_id)
        if "error" in result and not result.get("nodes"):
            raise HTTPException(404, result["error"])
        return {"status": "success", "graph": result}

    # ── GET /graph/citizen/{id} ──────────────────────────────────────────

    @router.get(
        "/citizen/{citizen_id}",
        summary="Get citizen subgraph",
    )
    async def get_citizen_graph(citizen_id: str) -> Dict[str, Any]:
        """
        Get the full subgraph around a citizen (2 hops).

        Shows all documents owned, cases linked, officers involved.
        """
        result = gov_kg.get_citizen_graph(citizen_id)
        if "error" in result and not result.get("nodes"):
            raise HTTPException(404, result["error"])
        return {"status": "success", "graph": result}

    # ── GET /graph/case/{id} ─────────────────────────────────────────────

    @router.get(
        "/case/{case_id}",
        summary="Get case subgraph",
    )
    async def get_case_graph(case_id: str) -> Dict[str, Any]:
        """
        Get the full subgraph around a case (2 hops).

        Shows linked documents, parties, officers, departments.
        """
        result = gov_kg.get_case_graph(case_id)
        if "error" in result and not result.get("nodes"):
            raise HTTPException(404, result["error"])
        return {"status": "success", "graph": result}

    # ── GET /graph/officer/{id} ──────────────────────────────────────────

    @router.get(
        "/officer/{officer_id}",
        summary="Get officer subgraph",
    )
    async def get_officer_graph(officer_id: str) -> Dict[str, Any]:
        """
        Get the full subgraph around an officer (2 hops).

        Shows documents verified/handled, department, cases.
        """
        result = gov_kg.get_officer_graph(officer_id)
        if "error" in result and not result.get("nodes"):
            raise HTTPException(404, result["error"])
        return {"status": "success", "graph": result}

    # ── GET /graph/stats ─────────────────────────────────────────────────

    @router.get("/stats", summary="Get graph statistics")
    async def get_stats() -> Dict[str, Any]:
        """
        Get statistics: total nodes, edges, type distribution, density,
        connected components.
        """
        return {"status": "success", "stats": gov_kg.get_stats()}

    # ── GET /graph/export ────────────────────────────────────────────────

    @router.get("/export", summary="Export full graph (D3.js format)")
    async def export_graph() -> Dict[str, Any]:
        """
        Export the full graph as D3.js-compatible JSON.

        Nodes include color by type. Edges include typed labels.
        Can be directly consumed by a D3.js force-directed graph.
        """
        return {"status": "success", "graph": gov_kg.export_graph_data()}

    # ── GET /graph/departments ───────────────────────────────────────────

    @router.get("/departments", summary="Get department graph")
    async def get_department_graph() -> Dict[str, Any]:
        """
        Department-centric view: departments with their officers,
        documents issued, and cases handled.
        """
        return {"status": "success", "graph": gov_kg.get_department_graph()}

    # ── GET /graph/timeline ──────────────────────────────────────────────

    @router.get("/timeline", summary="Get timeline graph")
    async def get_timeline_graph(
        entity_id: Optional[str] = Query(None, description="Entity ID to filter timeline"),
    ) -> Dict[str, Any]:
        """
        Chronological timeline of events extracted from graph node metadata.
        Optionally filtered to a specific entity.
        """
        return {
            "status": "success",
            "timeline": gov_kg.get_timeline_graph(entity_id),
        }

    # ── GET /graph/fraud-clusters ────────────────────────────────────────

    @router.get("/fraud-clusters", summary="Detect fraud clusters")
    async def detect_fraud_clusters(
        min_size: int = Query(3, ge=2, description="Minimum cluster size"),
    ) -> Dict[str, Any]:
        """
        Detect suspicious clusters of tightly connected entities.

        Returns clusters sorted by risk score.
        Indicators: single citizen with many docs, multiple cases,
        cross-department connections, dense subgraphs.
        """
        clusters = gov_kg.detect_fraud_clusters(min_cluster_size=min_size)
        return {
            "status": "success",
            "clusters": clusters,
            "cluster_count": len(clusters),
        }

    # ── GET /graph/duplicates ────────────────────────────────────────────

    @router.get("/duplicates", summary="Detect duplicate identities")
    async def detect_duplicates(
        threshold: int = Query(80, ge=50, le=99, description="Fuzzy match threshold (50-99)"),
    ) -> Dict[str, Any]:
        """
        Detect potential duplicate identities — citizens with similar names
        across documents.

        Returns pairs sorted by match score.
        """
        duplicates = gov_kg.detect_duplicate_identities(threshold)
        return {
            "status": "success",
            "duplicates": duplicates,
            "duplicate_count": len(duplicates),
        }

    # ── POST /graph/ingest ───────────────────────────────────────────────

    @router.post("/ingest", summary="Ingest document entities into graph")
    async def ingest_entities(body: IngestRequest) -> Dict[str, Any]:
        """
        Ingest extracted entities from a document into the knowledge graph.

        Creates nodes for the document, owner, and all extracted entities.
        Creates edges for ownership, issuance, verification, etc.

        This endpoint is typically called after the AI Engine extracts
        entities from a document.
        """
        # Build entity dict for ingestion
        entities = {
            "citizens": [_wrap(c) for c in body.citizens],
            "officers": [_wrap(o) for o in body.officers],
            "departments": [_wrap(d) for d in body.departments],
            "courts": [_wrap(c) for c in body.courts],
            "institutions": [_wrap(i) for i in body.institutions],
        }

        counts = gov_kg.ingest_document_entities(
            document_id=body.document_id,
            document_name=body.document_name,
            document_type=body.document_type,
            owner=body.owner,
            entities=entities,
            metadata=body.metadata,
        )

        # Also add explicit case nodes
        for case in body.cases:
            case_num = case.get("name", case.get("value", ""))
            if case_num:
                case_eid = gov_kg.add_case(case_num, case.get("metadata", {}))
                # Link to document
                doc_eid = gov_kg._doc_index.get(body.document_id)
                if doc_eid:
                    gov_kg.add_linked_case(doc_eid, case_eid)
                    counts["edges"] += 1
                counts["nodes"] += 1

        # Add location nodes
        for loc in body.locations:
            loc_name = loc.get("name", loc.get("value", ""))
            if loc_name:
                gov_kg.add_location(loc_name, loc.get("metadata", {}))
                counts["nodes"] += 1

        return {
            "status": "success",
            "counts": counts,
            "stats": gov_kg.get_stats(),
        }

    return router


# ── Helpers ──────────────────────────────────────────────────────────────────

class _EntityWrapper:
    """Simple wrapper to make dicts look like EntityProfile objects."""
    def __init__(self, data: Dict[str, Any]):
        self.name = data.get("name", data.get("value", ""))
        self.role = data.get("role", "")
        self.entity_type = data.get("entity_type", "")
        self.confidence = data.get("confidence", 0.0)


def _wrap(data: Dict[str, Any]) -> _EntityWrapper:
    return _EntityWrapper(data)
