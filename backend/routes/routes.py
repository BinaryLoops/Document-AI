"""
FastAPI routes for the RAG system API.
"""

import logging
import uuid
import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query, File, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
import tempfile
import os
import time
from PIL import Image

# Configure logging
logger = logging.getLogger(__name__)

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".docx", ".txt"}

# Optional Firebase import (Auth/Firestore remain unchanged)
try:
    from storage.firebase_client import get_db
    FIREBASE_AVAILABLE = True
    logger.info("Firebase client available")
except ImportError:
    FIREBASE_AVAILABLE = False
    logger.warning("Firebase not available - some features will be limited")

from document.ocr_processor import extract_text_from_image
from document.document_classifier import DocumentClassifier
from document.field_extractor import FieldExtractor
from document.staging_store import staging_store, StagedDocument
from storage.cloudinary_client import upload_bytes, delete_file

# Knowledge graph singleton
try:
    from knowledge_graph.kg_manager import kg_manager
    KG_AVAILABLE = True
    logger.info("Knowledge graph manager loaded")
except Exception as e:
    KG_AVAILABLE = False
    kg_manager = None
    logger.warning(f"Knowledge graph not available: {e}")

# Intelligence engines (lazy — only imported once, reused per request)
try:
    from knowledge_graph.intelligence import (
        EvidenceProvenanceEngine,
        CrossDocumentRelationEngine,
        CompletenessEngine,
        ContradictionEngine,
        VersionTracker,
        GraphRAGEngine,
        DocumentComparisonEngine,
        ExplainabilityEngine,
    )
    INTELLIGENCE_AVAILABLE = True
    logger.info("Intelligence engines loaded")
except Exception as _ie:
    INTELLIGENCE_AVAILABLE = False
    logger.warning(f"Intelligence engines not available: {_ie}")


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class DocumentInput(BaseModel):
    title: str
    text: str
    source: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentsInput(BaseModel):
    documents: List[DocumentInput]


class QueryInput(BaseModel):
    query: str
    top_k: int = 5
    search_type: str = "hybrid"
    filter_dict: Optional[Dict[str, Any]] = None
    max_tokens: int = 512
    use_kg: bool = False  # set True to get KG-enhanced context in response


class SearchResult(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any]
    score: float


class RAGResponse(BaseModel):
    query: str
    response: str
    retrieved_documents: List[SearchResult]
    search_type: str
    evidence: List[Dict[str, Any]] = []
    kg_context: Optional[Dict[str, Any]] = None  # populated when use_kg=True


class HealthResponse(BaseModel):
    status: str
    version: str
    document_count: int
    message: Optional[str] = None


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class RAGAPIRouter:
    """FastAPI router for the RAG system API."""

    def __init__(self, app: FastAPI, rag_engine):
        self.app = app
        self.rag_engine = rag_engine

        from embedding.model import create_embedding_model
        self.classifier = DocumentClassifier(create_embedding_model())
        self.extractor = FieldExtractor(self.rag_engine)

        self._register_routes()

    # -----------------------------------------------------------------------
    # Route registration
    # -----------------------------------------------------------------------

    def _register_routes(self):

        # -------------------------------------------------------------------
        # Documents
        # -------------------------------------------------------------------

        @self.app.post("/documents", response_model=Dict[str, Any],
                       summary="Add documents to the system", tags=["RAG"])
        async def add_documents(documents: DocumentsInput):
            try:
                texts = [doc.text for doc in documents.documents]
                metadata = [
                    {**doc.metadata, "title": doc.title,
                     "source": doc.source or "API upload"}
                    for doc in documents.documents
                ]
                doc_ids = self.rag_engine.add_documents(texts, metadata)
                return {
                    "status": "success",
                    "message": f"Added {len(doc_ids)} documents",
                    "document_ids": doc_ids,
                }
            except Exception as e:
                logger.error(f"Error adding documents: {e}")
                raise HTTPException(status_code=500,
                                    detail=f"Failed to add documents: {str(e)}")

        # -------------------------------------------------------------------
        # Upload
        # -------------------------------------------------------------------

        @self.app.post("/upload", response_model=Dict[str, Any],
                       summary="Upload and process document files", tags=["RAG"])
        async def upload_document(
            file: UploadFile = File(...),
            chunk_size: int = Query(1000, ge=100, le=5000),
            chunk_overlap: int = Query(200, ge=0, le=500),
            build_kg: bool = Query(True, description="Auto-populate knowledge graph after upload"),
        ):
            doc_id = str(uuid.uuid4())

            if FIREBASE_AVAILABLE:
                try:
                    db = get_db()
                    doc_ref = db.collection("documents").document(doc_id)
                except Exception:
                    db = doc_ref = None
            else:
                db = doc_ref = None

            def _fb_update(data: dict):
                if doc_ref:
                    try:
                        doc_ref.update(data)
                    except Exception:
                        pass

            try:
                from document.processor import DocumentProcessor

                start_time = time.time()
                content = await file.read()
                ext = os.path.splitext(file.filename)[1].lower()

                if not content:
                  raise HTTPException(status_code=400, detail="No file uploaded")
                if len(content) > _MAX_UPLOAD_BYTES:
                  raise HTTPException(status_code=413, detail="File too large")
                if ext not in _ALLOWED_EXTENSIONS:
                  raise HTTPException(status_code=400, detail="Unsupported file type")

                if doc_ref:
                    try:
                        doc_ref.set({
                            "filename": file.filename,
                            "status": "UPLOADED",
                            "upload_time": datetime.datetime.utcnow(),
                            "document_id": doc_id,
                        })
                    except Exception:
                        pass

                logger.info("Document upload started: %s", file.filename)
                try:
                  cloudinary_file = upload_bytes(
                    content,
                    public_id=doc_id,
                    filename=file.filename or f"{doc_id}{ext}",
                  )
                except Exception as upload_error:
                  logger.error("Cloudinary upload failed: %s", upload_error, exc_info=True)
                  raise HTTPException(status_code=500, detail="Cloudinary upload failed")
                _fb_update({
                  "fileUrl": cloudinary_file["fileUrl"],
                  "publicId": cloudinary_file["publicId"],
                  "uploadedAt": datetime.datetime.utcnow(),
                  "fileType": file.content_type or ext.lstrip("."),
                  "size": cloudinary_file["bytes"],
                  "resourceType": cloudinary_file["resourceType"],
                  "status": "PROCESSING",
                })
                logger.info("Document upload completed: %s", file.filename)

                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                    tmp.write(content)
                    temp_path = tmp.name

                try:
                    # OCR branch for images
                    if ext in (".jpg", ".jpeg", ".png"):
                        _fb_update({"status": "OCR"})
                        image = Image.open(temp_path)
                        try:
                            text, ocr_confidence = extract_text_from_image(image)
                        finally:
                            image.close()

                        if not text.strip():
                            _fb_update({"status": "FAILED",
                                        "error": "No text extracted via OCR"})
                            return {"status": "warning",
                                    "message": "No text extracted from image"}

                        chunks = [text]
                        chunk_metadata = [{
                            "filename": file.filename,
                            "source": file.filename,
                            "ocr_confidence": ocr_confidence,
                        }]
                        _fb_update({"ocr_confidence": ocr_confidence})
                    else:
                        _fb_update({"status": "EXTRACTING"})
                        processor = DocumentProcessor(
                            chunk_size=chunk_size, chunk_overlap=chunk_overlap
                        )
                        chunks, chunk_metadata = processor.process_file(
                            temp_path,
                            metadata={"filename": file.filename,
                                      "source": file.filename},
                        )

                    if not chunks:
                        _fb_update({"status": "FAILED",
                                    "error": "No text extracted from document"})
                        return {"status": "warning",
                                "message": "No text extracted from document"}

                    full_text = " ".join(chunks)

                    # Classification
                    _fb_update({"status": "CLASSIFYING"})
                    doc_type, classification_confidence = self.classifier.classify(
                        full_text
                    )
                    _fb_update({
                        "document_type": doc_type,
                        "classification_confidence": classification_confidence,
                    })

                    # Field extraction
                    _fb_update({"status": "EXTRACTING_FIELDS"})
                    extracted_fields = self.extractor.extract(
                        chunks, chunk_metadata, doc_type, file.filename
                    )
                    _fb_update({"extracted_fields": extracted_fields})

                    # Stamp chunk metadata
                    for m in chunk_metadata:
                        m["document_id"] = doc_id
                        m["document_type"] = doc_type
                        m["source"] = file.filename

                    # -------------------------------------------------------
                    # Stage for review — the document is fully analyzed but
                    # NOT yet indexed into RAG/KG or marked complete. The
                    # citizen reviews the detected type/fields and explicitly
                    # confirms (POST /upload/{document_id}/confirm) or
                    # discards (POST /upload/{document_id}/discard) before
                    # it becomes part of their permanent document record.
                    # -------------------------------------------------------
                    _fb_update({"status": "PENDING_REVIEW"})
                    staging_store.put(StagedDocument(
                        document_id=doc_id,
                        filename=file.filename,
                        ext=ext,
                        chunks=chunks,
                        chunk_metadata=chunk_metadata,
                        document_type=doc_type,
                        classification_confidence=float(classification_confidence),
                        extracted_fields=extracted_fields,
                        cloudinary_file=cloudinary_file,
                        build_kg=build_kg,
                        start_time=start_time,
                    ))

                    return {
                        "success": True,
                        "url": cloudinary_file["fileUrl"],
                        "publicId": cloudinary_file["publicId"],
                        "status": "pending_review",
                        "message": (
                            f"Analyzed document into {len(chunks)} chunk(s). "
                            "Review the detected details and confirm to save, "
                            "or discard to upload a different file."
                        ),
                        "document_id": doc_id,
                        "document_type": doc_type,
                        "classification_confidence": float(classification_confidence),
                        "extracted_fields": extracted_fields,
                        "chunk_count": len(chunks),
                        "processing_time_seconds": round(
                            time.time() - start_time, 2
                        ),
                        "firebase_enabled": FIREBASE_AVAILABLE,
                        "file_url": cloudinary_file["fileUrl"],
                        "public_id": cloudinary_file["publicId"],
                        "file_type": cloudinary_file["format"],
                        "file_size": cloudinary_file["bytes"],
                        "expires_in_seconds": staging_store.ttl_seconds,
                    }
                finally:
                    os.unlink(temp_path)

            except Exception as e:
                logger.error("Document upload failed: %s", e, exc_info=True)
                _fb_update({"status": "FAILED", "error": str(e)})
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to process document: {str(e)}",
                )

        # -------------------------------------------------------------------
        # Upload confirm / discard — completes the two-step review flow
        # -------------------------------------------------------------------

        def _doc_ref(doc_id: str):
            if not FIREBASE_AVAILABLE:
                return None
            try:
                return get_db().collection("documents").document(doc_id)
            except Exception:
                return None

        def _update_doc(doc_id: str, data: dict):
            ref = _doc_ref(doc_id)
            if ref:
                try:
                    ref.update(data)
                except Exception:
                    pass

        @self.app.post(
            "/upload/{document_id}/confirm",
            response_model=Dict[str, Any],
            summary="Confirm a staged upload and finalize it (index into RAG/KG)",
            tags=["RAG"],
        )
        async def confirm_upload(document_id: str):
            staged = staging_store.pop(document_id)
            if staged is None:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "No pending upload found for this document_id — it may "
                        "have already been confirmed/discarded, or the review "
                        "window expired. Please upload the file again."
                    ),
                )

            try:
                _update_doc(document_id, {"status": "INDEXING"})
                doc_ids = self.rag_engine.add_documents(
                    staged.chunks, staged.chunk_metadata
                )

                kg_stats = {}
                if staged.build_kg and KG_AVAILABLE:
                    kg_manager.process_extracted_fields(
                        document_id=staged.document_id,
                        filename=staged.filename,
                        document_type=staged.document_type,
                        extracted_fields=staged.extracted_fields,
                        chunks=staged.chunks,
                    )
                    kg_manager.process_document(staged.chunks, staged.chunk_metadata)
                    kg_stats = kg_manager.get_stats()

                _update_doc(document_id, {"status": "COMPLETED"})

                return {
                    "success": True,
                    "status": "success",
                    "message": f"Document confirmed and indexed into {len(staged.chunks)} chunks",
                    "document_id": staged.document_id,
                    "document_type": staged.document_type,
                    "classification_confidence": staged.classification_confidence,
                    "extracted_fields": staged.extracted_fields,
                    "chunk_count": len(staged.chunks),
                    "document_ids": doc_ids,
                    "processing_time_seconds": round(time.time() - staged.start_time, 2),
                    "firebase_enabled": FIREBASE_AVAILABLE,
                    "file_url": staged.cloudinary_file["fileUrl"],
                    "public_id": staged.cloudinary_file["publicId"],
                    "file_type": staged.cloudinary_file["format"],
                    "file_size": staged.cloudinary_file["bytes"],
                    "knowledge_graph": kg_stats,
                }
            except Exception as e:
                logger.error("Document confirm failed: %s", e, exc_info=True)
                _update_doc(document_id, {"status": "FAILED", "error": str(e)})
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to confirm document: {str(e)}",
                )

        @self.app.post(
            "/upload/{document_id}/discard",
            response_model=Dict[str, Any],
            summary="Discard a staged upload (e.g. wrong file, poor scan)",
            tags=["RAG"],
        )
        async def discard_upload(document_id: str):
            staged = staging_store.pop(document_id)
            if staged is None:
                # Already confirmed, already discarded, or the review window
                # expired — either way the client is free to upload again.
                return {
                    "success": True,
                    "status": "not_found",
                    "message": "No pending upload found for this document_id.",
                }

            try:
                resource_type = staged.cloudinary_file.get("resourceType", "raw")
                delete_file(staged.cloudinary_file["publicId"], resource_type=resource_type)
            except Exception as e:
                logger.warning("Failed to delete discarded Cloudinary asset: %s", e)

            _update_doc(document_id, {"status": "DISCARDED"})

            return {
                "success": True,
                "status": "discarded",
                "message": "Upload discarded. You can upload another document.",
                "document_id": document_id,
            }

        # -------------------------------------------------------------------
        # Document status
        # -------------------------------------------------------------------

        @self.app.get("/documents/{document_id}/status",
                      summary="Get document processing status", tags=["RAG"])
        async def get_document_status(document_id: str):
            if not FIREBASE_AVAILABLE:
                return {
                    "status": "error",
                    "message": "Firebase not available - status tracking disabled",
                    "document_id": document_id,
                }
            try:
                db = get_db()
                doc = db.collection("documents").document(document_id).get()
                if not doc.exists:
                    raise HTTPException(status_code=404,
                                        detail="Document not found")
                return doc.to_dict()
            except Exception as e:
                logger.error(f"Error fetching document status: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to fetch status: {str(e)}",
                )

        # -------------------------------------------------------------------
        # Query  (task 5 — use_kg flag)
        # -------------------------------------------------------------------

        @self.app.post("/query", response_model=RAGResponse,
                       summary="Query the RAG system", tags=["RAG"])
        async def query(query_input: QueryInput):
            try:
                logger.info(f"Processing query: {query_input.query}")
                result = self.rag_engine.generate_response(
                    query=query_input.query,
                    top_k=query_input.top_k,
                    search_type=query_input.search_type,
                    filter_dict=query_input.filter_dict,
                    max_tokens=query_input.max_tokens,
                )

                # Optional KG context enrichment
                kg_context = None
                if query_input.use_kg and KG_AVAILABLE:
                    try:
                        # Find entities in the query and pull their graph neighbours
                        words = [
                            w.strip("?,.")
                            for w in query_input.query.split()
                            if len(w) > 3
                        ]
                        hits = []
                        seen = set()
                        for word in words:
                            res = kg_manager.get_entity(word)
                            if res.get("found") and res["name"] not in seen:
                                seen.add(res["name"])
                                hits.append(res)
                        kg_context = {
                            "matched_entities": hits,
                            "stats": kg_manager.get_stats(),
                        }
                    except Exception as kg_err:
                        logger.warning(f"KG context enrichment failed: {kg_err}")
                        kg_context = {"error": str(kg_err)}

                return RAGResponse(
                    query=result["query"],
                    response=result["response"],
                    retrieved_documents=[
                        SearchResult(
                            id=doc["id"],
                            text=doc["text"],
                            metadata=doc["metadata"],
                            score=float(doc["score"]),
                        )
                        for doc in result["retrieved_documents"]
                    ],
                    search_type=result["search_type"],
                    evidence=[
                        {
                            "source_document": doc["metadata"].get(
                                "source", "Unknown"
                            ),
                            "page": doc["metadata"].get("page", "unknown"),
                            "evidence_snippet": doc["text"][:200],
                            "confidence": round(float(doc["score"]), 3),
                        }
                        for doc in result["retrieved_documents"]
                    ],
                    kg_context=kg_context,
                )
            except Exception as e:
                logger.error(f"Error querying RAG system: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to query system: {str(e)}",
                )

        # -------------------------------------------------------------------
        # Search
        # -------------------------------------------------------------------

        @self.app.get("/search",
                      summary="Search for documents without generating a response", tags=["RAG"])
        async def search(
            query: str,
            top_k: int = Query(5, ge=1, le=20),
            search_type: str = Query(
                "hybrid", regex="^(semantic|keyword|hybrid)$"
            ),
        ):
            try:
                results = self.rag_engine.search(
                    query=query, top_k=top_k, search_type=search_type
                )
                return {
                    "query": query,
                    "results": results,
                    "search_type": search_type,
                    "count": len(results),
                }
            except Exception as e:
                logger.error(f"Error searching documents: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to search documents: {str(e)}",
                )

        # -------------------------------------------------------------------
        # Delete all
        # -------------------------------------------------------------------

        @self.app.delete("/documents",
                         summary="Clear all documents from the system", tags=["RAG"])
        async def clear_documents():
            try:
                self.rag_engine.clear_documents()
                return {
                    "status": "success",
                    "message": "All documents cleared from the system",
                }
            except Exception as e:
                logger.error(f"Error clearing documents: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to clear documents: {str(e)}",
                )

        # -------------------------------------------------------------------
        # Health
        # -------------------------------------------------------------------

        @self.app.get("/rag/health", response_model=HealthResponse,
                      summary="RAG subsystem health (embedder + vector DB)", tags=["RAG"])
        async def health_check():
            try:
                doc_count = self.rag_engine.count_documents()
                return HealthResponse(
                    status="healthy",
                    version="1.0.0",
                    document_count=doc_count,
                    message="System is operational",
                )
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return HealthResponse(
                    status="unhealthy",
                    version="1.0.0",
                    document_count=0,
                    message=f"System error: {str(e)}",
                )

        # ===================================================================
        # Knowledge Graph endpoints  (tasks 3 & 4)
        # ===================================================================

        @self.app.get("/kg/stats",
                      summary="Knowledge graph statistics", tags=["Knowledge Graph"])
        async def kg_stats():
            """Return entity/relation counts and type breakdowns."""
            if not KG_AVAILABLE:
                raise HTTPException(
                    status_code=503, detail="Knowledge graph not available"
                )
            return kg_manager.get_stats()

        @self.app.get("/kg/graph",
                      summary="Knowledge graph nodes and links for visualisation", tags=["Knowledge Graph"])
        async def kg_graph(
            max_nodes: int = Query(
                100, ge=10, le=500,
                description="Maximum nodes to return (most connected first)"
            )
        ):
            """
            Return the graph as { nodes: [...], links: [...] } suitable for
            D3.js / Flutter force-directed rendering.
            """
            if not KG_AVAILABLE:
                raise HTTPException(
                    status_code=503, detail="Knowledge graph not available"
                )
            return kg_manager.get_graph_data(max_nodes=max_nodes)

        @self.app.get("/kg/entity/{name}",
                      summary="Look up a knowledge graph entity by name", tags=["Knowledge Graph"])
        async def kg_entity(name: str):
            """
            Return entity details and all immediate connections.
            Supports partial / case-insensitive matching.
            """
            if not KG_AVAILABLE:
                raise HTTPException(
                    status_code=503, detail="Knowledge graph not available"
                )
            result = kg_manager.get_entity(name)
            if not result.get("found"):
                raise HTTPException(
                    status_code=404,
                    detail=f"Entity '{name}' not found in knowledge graph",
                )
            return result

        @self.app.post("/kg/build",
                       summary="(Re)build knowledge graph from indexed documents", tags=["Knowledge Graph"])
        async def kg_build(
            reset: bool = Query(
                False,
                description="If true, clear existing KG before rebuilding"
            )
        ):
            """
            Trigger a full rebuild of the knowledge graph from every document
            currently indexed in the FAISS vector store.
            """
            if not KG_AVAILABLE:
                raise HTTPException(
                    status_code=503, detail="Knowledge graph not available"
                )
            result = kg_manager.build_from_rag(self.rag_engine, reset=reset)
            if result.get("status") == "error":
                raise HTTPException(status_code=500, detail=result["message"])
            return result

        @self.app.delete("/kg",
                         summary="Clear the knowledge graph", tags=["Knowledge Graph"])
        async def kg_clear():
            """Remove all entities and relations from the knowledge graph."""
            if not KG_AVAILABLE:
                raise HTTPException(
                    status_code=503, detail="Knowledge graph not available"
                )
            kg_manager.clear()
            return {"status": "success", "message": "Knowledge graph cleared"}

        # ===================================================================
        # Intelligence endpoints  (8 features)
        # ===================================================================

        def _require_intelligence():
            if not INTELLIGENCE_AVAILABLE:
                raise HTTPException(
                    status_code=503,
                    detail="Intelligence engines not available. Check server logs.",
                )

        # -------------------------------------------------------------------
        # 1. Evidence / Source Provenance
        # -------------------------------------------------------------------

        @self.app.post(
            "/intelligence/provenance",
            summary="Build evidence chain for a query answer",
            tags=["RAG Intelligence"],
        )
        async def intelligence_provenance(query_input: QueryInput):
            """
            Run a standard RAG query then return a full source-provenance
            record: which chunks were used, their relevance scores, KG
            entities found, and whether the answer is grounded.
            """
            _require_intelligence()
            try:
                rag_result = self.rag_engine.generate_response(
                    query=query_input.query,
                    top_k=query_input.top_k,
                    search_type=query_input.search_type,
                    filter_dict=query_input.filter_dict,
                    max_tokens=query_input.max_tokens,
                )
                engine = EvidenceProvenanceEngine(kg_manager=kg_manager)
                provenance = engine.build_evidence_chain(
                    query=query_input.query,
                    retrieved_docs=rag_result.get("retrieved_documents", []),
                    response=rag_result.get("response", ""),
                )
                return {"response": rag_result.get("response", ""), **provenance}
            except Exception as e:
                logger.error(f"Provenance error: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        # -------------------------------------------------------------------
        # 2. Cross-Document Relationships
        # -------------------------------------------------------------------

        @self.app.post(
            "/intelligence/cross-doc",
            summary="Find shared entities / values across uploaded documents",
            tags=["RAG Intelligence"],
        )
        async def intelligence_cross_doc(
            document_fields: List[Dict[str, Any]],
        ):
            """
            Pass a list of documents (each with `document_id`, `filename`,
            `document_type`, `extracted_fields`) to discover which entities
            and field values are shared across them, and link them in the KG.

            Example body:
            ```json
            [
              {"document_id": "abc", "filename": "id.png",
               "document_type": "Identity Proof",
               "extracted_fields": [{"field": "full_name", "value": "Ravi Kumar"}]},
              {"document_id": "xyz", "filename": "app.pdf",
               "document_type": "Application",
               "extracted_fields": [{"field": "applicant_name", "value": "Ravi Kumar"}]}
            ]
            ```
            """
            _require_intelligence()
            try:
                engine = CrossDocumentRelationEngine(kg_manager=kg_manager)
                result = engine.build_cross_doc_map(document_fields)
                entity_map = engine.get_entity_document_map()
                return {**result, "entity_document_map": entity_map}
            except Exception as e:
                logger.error(f"Cross-doc error: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        # -------------------------------------------------------------------
        # 3. Document Completeness
        # -------------------------------------------------------------------

        class CompletenessRequest(BaseModel):
            document_type: str
            extracted_fields: List[Dict[str, Any]] = []
            workflow: Optional[str] = None
            uploaded_document_types: Optional[List[str]] = None

        @self.app.post(
            "/intelligence/completeness",
            summary="Check field and workflow completeness",
            tags=["RAG Intelligence"],
        )
        async def intelligence_completeness(req: CompletenessRequest):
            """
            Two checks in one call:
            - **Field completeness**: are all required fields present for
              this `document_type`?
            - **Workflow completeness** (optional): pass `workflow` and
              `uploaded_document_types` to check if the full document set
              for a workflow (e.g. `GOVERNMENT_APPLICATION`) is present.

            Available workflows: `GOVERNMENT_APPLICATION`, `COURT_CASE`,
            `NOTARY`, `KYC`.
            """
            _require_intelligence()
            try:
                engine = CompletenessEngine()
                field_result = engine.check_document_fields(
                    req.document_type, req.extracted_fields
                )
                workflow_result = None
                if req.workflow and req.uploaded_document_types is not None:
                    workflow_result = engine.check_workflow(
                        req.workflow, req.uploaded_document_types
                    )
                return {
                    "field_completeness": field_result,
                    "workflow_completeness": workflow_result,
                }
            except Exception as e:
                logger.error(f"Completeness error: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        # -------------------------------------------------------------------
        # 4. Contradiction Detection
        # -------------------------------------------------------------------

        @self.app.post(
            "/intelligence/contradictions",
            summary="Detect field-level contradictions across documents",
            tags=["RAG Intelligence"],
        )
        async def intelligence_contradictions(
            document_fields: List[Dict[str, Any]],
        ):
            """
            Pass 2+ documents (each with `extracted_fields`) and get back
            every field where values disagree, with severity
            (`MINOR` / `MODERATE` / `MAJOR`) and a plain-English explanation.
            """
            _require_intelligence()
            try:
                engine = ContradictionEngine()
                return engine.detect(document_fields)
            except Exception as e:
                logger.error(f"Contradiction error: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        # -------------------------------------------------------------------
        # 5. Version / Supersession Tracking
        # -------------------------------------------------------------------

        class VersionRequest(BaseModel):
            document_a: Dict[str, Any]
            document_b: Dict[str, Any]

        @self.app.post(
            "/intelligence/version",
            summary="Detect if one document supersedes another",
            tags=["RAG Intelligence"],
        )
        async def intelligence_version(req: VersionRequest):
            """
            Compare two documents and determine if they are different versions
            of the same document. Returns:
            - `likely_versions_of_same_document`: bool
            - `newer_document`: document_id of the newer one
            - `supersedes`: which doc is superseded
            - `changed_fields`: list of field-level changes
            """
            _require_intelligence()
            try:
                tracker = VersionTracker()
                # Provide embedder if available
                embedder = getattr(self.rag_engine, "embedder", None)
                return tracker.compare_versions(
                    req.document_a, req.document_b, embedder=embedder
                )
            except Exception as e:
                logger.error(f"Version tracking error: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        # -------------------------------------------------------------------
        # 6. GraphRAG
        # -------------------------------------------------------------------

        @self.app.post(
            "/intelligence/graphrag",
            summary="KG-guided retrieval + answer generation",
            tags=["RAG Intelligence"],
        )
        async def intelligence_graphrag(query_input: QueryInput):
            """
            Enhanced RAG that:
            1. Extracts named entities from the query via the KG
            2. Retrieves candidate chunks from FAISS
            3. Re-ranks chunks using KG proximity
            4. Generates an answer with KG context injected

            Returns the answer, evidence, matched KG entities, and the
            KG context string used.
            """
            _require_intelligence()
            try:
                engine = GraphRAGEngine(
                    rag_engine=self.rag_engine, kg_manager=kg_manager
                )
                return engine.query(
                    query=query_input.query,
                    top_k=query_input.top_k,
                    max_tokens=query_input.max_tokens,
                )
            except Exception as e:
                logger.error(f"GraphRAG error: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        # -------------------------------------------------------------------
        # 7. Document Comparison
        # -------------------------------------------------------------------

        class CompareRequest(BaseModel):
            document_a: Dict[str, Any]
            document_b: Dict[str, Any]

        @self.app.post(
            "/intelligence/compare",
            summary="Structured side-by-side document comparison",
            tags=["RAG Intelligence"],
        )
        async def intelligence_compare(req: CompareRequest):
            """
            Full field-level diff between two documents:
            - Per-field status: `MATCH` / `NEAR_MATCH` / `MISMATCH` /
              `ONLY_IN_A` / `ONLY_IN_B`
            - Similarity scores (field-level + full content)
            - Completeness delta
            - Verdict string
            """
            _require_intelligence()
            try:
                engine = DocumentComparisonEngine()
                embedder = getattr(self.rag_engine, "embedder", None)
                return engine.compare(
                    req.document_a, req.document_b, embedder=embedder
                )
            except Exception as e:
                logger.error(f"Comparison error: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        # -------------------------------------------------------------------
        # 8. Explainability / "Why?"
        # -------------------------------------------------------------------

        @self.app.post(
            "/intelligence/explain",
            summary="Explain why the system gave a particular answer",
            tags=["RAG Intelligence"],
        )
        async def intelligence_explain(query_input: QueryInput):
            """
            Runs the query then returns a step-by-step trace of the
            reasoning process:
            - Which search type was used
            - Which chunks were retrieved and why
            - Which KG entities matched
            - Confidence level breakdown
            - Human-readable narrative explanation
            """
            _require_intelligence()
            try:
                rag_result = self.rag_engine.generate_response(
                    query=query_input.query,
                    top_k=query_input.top_k,
                    search_type=query_input.search_type,
                    filter_dict=query_input.filter_dict,
                    max_tokens=query_input.max_tokens,
                )
                # Collect KG entities for the query
                kg_entities: List[Dict] = []
                if kg_manager and KG_AVAILABLE:
                    for word in query_input.query.split():
                        word = word.strip("?,.")
                        if len(word) > 3:
                            res = kg_manager.get_entity(word)
                            if res.get("found"):
                                kg_entities.append(res)

                engine = ExplainabilityEngine()
                return engine.explain(
                    query=query_input.query,
                    rag_result=rag_result,
                    kg_entities=kg_entities,
                )
            except Exception as e:
                logger.error(f"Explain error: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        # ===================================================================
        # KG Visualize (existing endpoint — kept at the end)
        # ===================================================================

        @self.app.get("/kg/visualize",
                      response_class=HTMLResponse,
                      summary="Interactive HTML visualisation of the knowledge graph", tags=["Knowledge Graph"])
        async def kg_visualize(
            max_nodes: int = Query(80, ge=10, le=300,
                                   description="Max nodes (most connected first)")
        ):
            if not KG_AVAILABLE:
                raise HTTPException(status_code=503, detail="Knowledge graph not available")
            try:
                graph_data = kg_manager.get_graph_data(max_nodes=max_nodes)
                stats      = kg_manager.get_stats()

                import json as _json
                nodes_json = _json.dumps(graph_data["nodes"])
                links_json = _json.dumps(graph_data["links"])
                stats_json = _json.dumps(stats)

                html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DocuMind Knowledge Graph</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#0d1117;color:#e6edf3;height:100vh;display:flex;flex-direction:column;overflow:hidden}}

/* top bar */
#topbar{{background:#161b22;border-bottom:1px solid #30363d;padding:8px 16px;display:flex;align-items:center;gap:12px;flex-shrink:0}}
#topbar h1{{font-size:14px;font-weight:600;color:#a78bfa;letter-spacing:.4px;margin-right:8px}}
.pill{{background:#21262d;border:1px solid #30363d;border-radius:20px;padding:2px 10px;font-size:11px;color:#8b949e}}
.pill b{{color:#e6edf3}}
.pill.tip{{margin-left:auto;font-size:10px;color:#484f58}}

/* layout */
#main{{flex:1;display:flex;overflow:hidden}}
#canvas{{flex:1;position:relative;background:#0d1117}}
svg{{width:100%;height:100%}}

/* edges */
.link{{stroke-opacity:.55;fill:none}}
.link.semantic{{stroke:#a78bfa;stroke-width:1.8px}}
.link.extracted{{stroke:#30363d;stroke-width:1px;stroke-dasharray:4 3}}
.link.highlighted{{stroke:#f78166!important;stroke-width:2.5px!important;stroke-opacity:1!important}}

/* edge labels — always visible */
.edge-label{{
  font-size:9.5px;
  font-weight:600;
  fill:#a78bfa;
  pointer-events:none;
  text-anchor:middle;
  dominant-baseline:middle;
  paint-order:stroke;
  stroke:#0d1117;
  stroke-width:3px;
  letter-spacing:.3px;
}}
.edge-label.extracted-lbl{{fill:#484f58;}}

/* nodes */
.node circle{{cursor:pointer;stroke:#0d1117;stroke-width:2px;transition:all .15s}}
.node circle:hover{{stroke:#e6edf3;stroke-width:2.5px}}
.node.selected circle{{stroke:#f0f6fc;stroke-width:3px}}
.node-label{{font-size:11px;fill:#c9d1d9;pointer-events:none;font-weight:500}}

/* edge tooltip */
#edge-tip{{position:absolute;background:#161b22;border:1px solid #30363d;border-radius:6px;padding:4px 10px;font-size:11px;color:#a78bfa;pointer-events:none;display:none;white-space:nowrap}}

/* right panel */
#panel{{width:260px;background:#161b22;border-left:1px solid #30363d;padding:14px;overflow-y:auto;flex-shrink:0}}
#panel h2{{font-size:12px;text-transform:uppercase;letter-spacing:.6px;color:#a78bfa;margin-bottom:10px}}
.ph{{color:#484f58;font-size:12px}}
.etype-badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600;margin-bottom:8px}}
.entity-name{{font-size:14px;font-weight:600;color:#f0f6fc;margin-bottom:12px;word-break:break-word}}
.section-hd{{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:#484f58;margin:10px 0 5px}}
.conn-row{{display:flex;gap:6px;align-items:flex-start;margin-bottom:5px;padding-left:6px;border-left:2px solid #21262d}}
.rel-chip{{background:#21262d;border-radius:3px;padding:1px 5px;font-size:10px;color:#8b949e;white-space:nowrap;flex-shrink:0}}
.conn-name{{font-size:12px;color:#c9d1d9;word-break:break-word}}

/* legend */
#legend{{position:absolute;bottom:14px;left:14px;background:rgba(22,27,34,.92);border:1px solid #30363d;border-radius:8px;padding:10px 14px}}
#legend h3{{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:#484f58;margin-bottom:7px}}
.leg-row{{display:flex;align-items:center;gap:7px;margin-bottom:4px;font-size:11px;color:#8b949e}}
.leg-dot{{width:11px;height:11px;border-radius:50%;flex-shrink:0}}

/* toggle + search */
#controls{{position:absolute;top:12px;left:12px;display:flex;gap:8px;align-items:center}}
#search{{background:#161b22;border:1px solid #30363d;border-radius:6px;color:#e6edf3;padding:5px 10px;font-size:12px;width:180px;outline:none}}
#search:focus{{border-color:#a78bfa}}
#search::placeholder{{color:#484f58}}
.toggle-btn{{background:#21262d;border:1px solid #30363d;border-radius:6px;color:#8b949e;padding:5px 10px;font-size:11px;cursor:pointer}}
.toggle-btn.active{{background:#a78bfa22;border-color:#a78bfa;color:#a78bfa}}
</style>
</head>
<body>
<div id="topbar">
  <h1>&#9672; DocuMind Knowledge Graph</h1>
  <span class="pill">Entities <b id="s-ent">-</b></span>
  <span class="pill">Relations <b id="s-rel">-</b></span>
  <span class="pill">Showing <b id="s-shown">-</b></span>
  <span class="pill tip">Click node &nbsp;|&nbsp; Scroll zoom &nbsp;|&nbsp; Drag to move</span>
</div>
<div id="main">
  <div id="canvas">
    <div id="controls">
      <input id="search" type="text" placeholder="&#128269; Search…">
      <button class="toggle-btn active" id="btn-extracted" onclick="toggleExtracted()">EXTRACTED_FROM</button>
    </div>
    <div id="legend"></div>
    <div id="edge-tip"></div>
  </div>
  <div id="panel">
    <h2>Entity Details</h2>
    <p class="ph">Click any node to inspect it.</p>
  </div>
</div>

<script>
const ALL_NODES = {nodes_json};
const ALL_LINKS = {links_json};
const STATS     = {stats_json};

document.getElementById('s-ent').textContent   = STATS.entity_count   ?? ALL_NODES.length;
document.getElementById('s-rel').textContent   = STATS.relation_count ?? ALL_LINKS.length;

// ── Colours ────────────────────────────────────────────────────────────────
const C = {{
  Person:'#818cf8', Organization:'#f472b6', Location:'#34d399',
  Date:'#fbbf24', Identifier:'#60a5fa', Concept:'#60a5fa',
  Attribute:'#94a3b8', Document:'#475569', DocumentField:'#2dd4bf', Other:'#6b7280'
}};
const col = t => C[t] || C.Other;

// ── Legend ─────────────────────────────────────────────────────────────────
const types = [...new Set(ALL_NODES.map(n=>n.type))];
const legEl = document.getElementById('legend');
legEl.innerHTML = '<h3>Entity types</h3>' +
  types.map(t=>`<div class="leg-row"><div class="leg-dot" style="background:${{col(t)}}"></div>${{t}}</div>`).join('');

// ── Show/hide EXTRACTED_FROM ───────────────────────────────────────────────
let showExtracted = true;
function toggleExtracted(){{
  showExtracted = !showExtracted;
  document.getElementById('btn-extracted').classList.toggle('active', showExtracted);
  linkSel.style('display', d => (!showExtracted && d.type==='EXTRACTED_FROM') ? 'none' : null);
  edgeTipLinks.style('display', d => (!showExtracted && d.type==='EXTRACTED_FROM') ? 'none' : null);
  edgeLabelSel.style('display', d => (!showExtracted && d.type==='EXTRACTED_FROM') ? 'none' : null);
}}

// ── SVG ────────────────────────────────────────────────────────────────────
const canvas = document.getElementById('canvas');
const W = canvas.clientWidth, H = canvas.clientHeight;
const svg = d3.select('#canvas').append('svg');

svg.append('defs').selectAll('marker')
  .data(['semantic','extracted','highlighted'])
  .enter().append('marker')
  .attr('id', d=>'arr-'+d)
  .attr('viewBox','0 -4 8 8').attr('refX',20).attr('refY',0)
  .attr('markerWidth',5).attr('markerHeight',5).attr('orient','auto')
  .append('path').attr('d','M0,-4L8,0L0,4')
  .attr('fill', d => d==='highlighted'?'#f78166': d==='semantic'?'#a78bfa':'#30363d');

const zoomG = svg.append('g');
svg.call(d3.zoom().scaleExtent([.1,8]).on('zoom',e=>zoomG.attr('transform',e.transform)));

// ── Clone data ─────────────────────────────────────────────────────────────
const nodes = ALL_NODES.map(d=>({{...d}}));
const links = ALL_LINKS.map(d=>({{...d}}));

document.getElementById('s-shown').textContent = nodes.length + ' nodes';

// ── Radial initial positions ───────────────────────────────────────────────
// Person → dead center; Dates/IDs/Attributes → inner ring; Document → outer ring
const personNodes   = nodes.filter(n=>n.type==='Person');
const docNodes      = nodes.filter(n=>n.type==='Document');
const otherNodes    = nodes.filter(n=>n.type!=='Person'&&n.type!=='Document');

personNodes.forEach(n=>{{ n.fx=W/2; n.fy=H/2; }});

docNodes.forEach((n,i)=>{{
  const angle = (i/Math.max(docNodes.length,1))*2*Math.PI - Math.PI/2;
  n.x = W/2 + 240*Math.cos(angle);
  n.y = H/2 + 240*Math.sin(angle);
}});

otherNodes.forEach((n,i)=>{{
  const angle = (i/Math.max(otherNodes.length,1))*2*Math.PI - Math.PI/2;
  n.x = W/2 + 140*Math.cos(angle);
  n.y = H/2 + 140*Math.sin(angle);
}});

// ── Force simulation ───────────────────────────────────────────────────────
const sim = d3.forceSimulation(nodes)
  .force('link', d3.forceLink(links).id(d=>d.id)
    .distance(d => d.type==='EXTRACTED_FROM' ? 180 : 110)
    .strength(d => d.type==='EXTRACTED_FROM' ? 0.2 : 0.7))
  .force('charge', d3.forceManyBody().strength(-400))
  .force('center', d3.forceCenter(W/2, H/2))
  .force('collide', d3.forceCollide().radius(d=>{{
    if(d.type==='Person') return 60;
    if(d.type==='Document') return 50;
    return 40;
  }}))
  .force('radial_person',
    d3.forceRadial(0, W/2, H/2).strength(d=>d.type==='Person'?1:0))
  .force('radial_doc',
    d3.forceRadial(220, W/2, H/2).strength(d=>d.type==='Document'?.4:0))
  .force('radial_field',
    d3.forceRadial(130, W/2, H/2).strength(d=>
      !['Person','Document'].includes(d.type)?.3:0));

// ── Draw links ─────────────────────────────────────────────────────────────
const linkSel = zoomG.append('g').selectAll('line')
  .data(links).enter().append('line')
  .attr('class', d => 'link ' + (d.type==='EXTRACTED_FROM'?'extracted':'semantic'))
  .attr('marker-end', d => `url(#arr-${{d.type==='EXTRACTED_FROM'?'extracted':'semantic'}})`);

// Always-visible edge labels
const edgeLabelSel = zoomG.append('g').selectAll('text')
  .data(links).enter().append('text')
  .attr('class', d => 'edge-label' + (d.type==='EXTRACTED_FROM'?' extracted-lbl':''))
  .text(d => d.type==='EXTRACTED_FROM' ? '' : d.type);   // hide EXTRACTED_FROM labels by default

// Invisible wider lines for edge hover tooltip
const edgeTipLinks = zoomG.append('g').selectAll('line')
  .data(links).enter().append('line')
  .style('stroke','transparent').style('stroke-width','12px')
  .style('cursor','default')
  .on('mousemove', (event,d)=>{{
    const tip = document.getElementById('edge-tip');
    tip.textContent = d.type;
    tip.style.display='block';
    tip.style.left=(event.offsetX+12)+'px';
    tip.style.top=(event.offsetY-10)+'px';
  }})
  .on('mouseleave', ()=>{{document.getElementById('edge-tip').style.display='none';}});

// ── Draw nodes ─────────────────────────────────────────────────────────────
const nodeSel = zoomG.append('g').selectAll('g')
  .data(nodes).enter().append('g').attr('class','node')
  .call(d3.drag()
    .on('start',(e,d)=>{{if(!e.active)sim.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y;}})
    .on('drag', (e,d)=>{{d.fx=e.x;d.fy=e.y;}})
    .on('end',  (e,d)=>{{if(!e.active)sim.alphaTarget(0);
      // keep Person pinned to center after drag
      if(d.type!=='Person'){{d.fx=null;d.fy=null;}}
    }}))
  .on('click', onNodeClick);

nodeSel.append('circle')
  .attr('r', d=>{{
    if(d.type==='Person')   return 22;
    if(d.type==='Document') return 16;
    return 10;
  }})
  .attr('fill', d=>col(d.type));

// Node labels — show below for Person, right for others
nodeSel.append('text').attr('class','node-label')
  .attr('text-anchor', d=>d.type==='Person'?'middle':'start')
  .attr('x', d=>d.type==='Person'?0:14)
  .attr('y', d=>d.type==='Person'?34:4)
  .text(d=>d.name.length>24?d.name.slice(0,22)+'…':d.name);

// ── Tick ───────────────────────────────────────────────────────────────────
sim.on('tick',()=>{{
  linkSel
    .attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
    .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
  edgeTipLinks
    .attr('x1',d=>d.source.x).attr('y1',d=>d.source.y)
    .attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
  // Position label at midpoint, slightly offset perpendicular to edge
  edgeLabelSel
    .attr('x', d=>{{
      const mx=(d.source.x+d.target.x)/2;
      const dy=d.target.y-d.source.y;
      const dx=d.target.x-d.source.x;
      const len=Math.sqrt(dx*dx+dy*dy)||1;
      return mx - (dy/len)*10;  // perpendicular offset
    }})
    .attr('y', d=>{{
      const my=(d.source.y+d.target.y)/2;
      const dy=d.target.y-d.source.y;
      const dx=d.target.x-d.source.x;
      const len=Math.sqrt(dx*dx+dy*dy)||1;
      return my + (dx/len)*10;
    }});
  nodeSel.attr('transform',d=>`translate(${{d.x}},${{d.y}})`);
}});

// ── Node click ─────────────────────────────────────────────────────────────
function onNodeClick(event,d){{
  event.stopPropagation();
  nodeSel.classed('selected',n=>n.id===d.id);
  linkSel.classed('highlighted',l=>l.source.id===d.id||l.target.id===d.id)
         .attr('marker-end',l=>
           l.source.id===d.id||l.target.id===d.id
             ?'url(#arr-highlighted)'
             :`url(#arr-${{l.type==='EXTRACTED_FROM'?'extracted':'semantic'}})`);

  const out = links.filter(l=>l.source.id===d.id);
  const inc = links.filter(l=>l.target.id===d.id);
  const byId = id=>nodes.find(n=>n.id===id)||{{}};

  document.getElementById('panel').innerHTML=`
    <h2>Entity Details</h2>
    <div class="etype-badge" style="background:${{col(d.type)}}22;color:${{col(d.type)}};border:1px solid ${{col(d.type)}}44">${{d.type}}</div>
    <div class="entity-name">${{d.name}}</div>
    ${{out.length?`<div class="section-hd">&#8594; outgoing (${{out.length}})</div>`+
      out.map(l=>`<div class="conn-row"><span class="rel-chip">${{l.type}}</span><span class="conn-name">${{byId(l.target.id).name||l.target.id}}</span></div>`).join(''):''}}
    ${{inc.length?`<div class="section-hd">&#8592; incoming (${{inc.length}})</div>`+
      inc.map(l=>`<div class="conn-row"><span class="rel-chip">${{l.type}}</span><span class="conn-name">${{byId(l.source.id).name||l.source.id}}</span></div>`).join(''):''}}
    ${{!out.length&&!inc.length?'<div class="section-hd">No connections yet</div>':''}}
  `;
}}

svg.on('click',()=>{{
  nodeSel.classed('selected',false);
  linkSel.classed('highlighted',false)
         .attr('marker-end',d=>`url(#arr-${{d.type==='EXTRACTED_FROM'?'extracted':'semantic'}})`);
  document.getElementById('panel').innerHTML=
    '<h2>Entity Details</h2><p class="ph">Click any node to inspect it.</p>';
}});

// ── Search ─────────────────────────────────────────────────────────────────
document.getElementById('search').addEventListener('input',function(){{
  const q=this.value.toLowerCase().trim();
  if(!q){{
    nodeSel.style('opacity',1);
    linkSel.style('opacity',null);
    return;
  }}
  const hit=new Set(nodes.filter(n=>n.name.toLowerCase().includes(q)).map(n=>n.id));
  nodeSel.style('opacity',d=>hit.has(d.id)?1:.08);
  linkSel.style('opacity',l=>hit.has(l.source.id)||hit.has(l.target.id)?.9:.04);
  if(hit.size===1){{
    const n=nodes.find(n=>hit.has(n.id));
    if(n) onNodeClick({{stopPropagation:()=>{{}}}},n);
  }}
}});
</script>
</body></html>"""
                return HTMLResponse(content=html)
            except Exception as e:
                logger.error(f"KG visualize failed: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=f"Failed to generate visualisation: {str(e)}")

                # Filter: only keep nodes that have at least one edge
                linked_ids = set()
                for lnk in graph_data["links"]:
                    linked_ids.add(lnk["source"])
                    linked_ids.add(lnk["target"])

                # If nothing is connected yet, show all nodes so the page
                # isn't blank on first upload
                nodes_to_show = (
                    [n for n in graph_data["nodes"] if n["id"] in linked_ids]
                    or graph_data["nodes"]
                )
                node_ids_shown = {n["id"] for n in nodes_to_show}
                links_to_show = [
                    l for l in graph_data["links"]
                    if l["source"] in node_ids_shown and l["target"] in node_ids_shown
                ]

                import json as _json
                nodes_json = _json.dumps(nodes_to_show)
                links_json = _json.dumps(links_to_show)
                stats_json = _json.dumps(stats)

                html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DocuMind Knowledge Graph</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', sans-serif; background: #0f1117; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }}

  /* ── Top bar ── */
  #topbar {{
    background: #1a1d27;
    border-bottom: 1px solid #2d3048;
    padding: 10px 18px;
    display: flex;
    align-items: center;
    gap: 20px;
    flex-shrink: 0;
  }}
  #topbar h1 {{ font-size: 15px; font-weight: 600; color: #a78bfa; letter-spacing: .5px; }}
  .stat-pill {{
    background: #2d3048;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 12px;
    color: #94a3b8;
  }}
  .stat-pill b {{ color: #e2e8f0; }}

  /* ── Main area ── */
  #main {{ flex: 1; display: flex; overflow: hidden; }}

  /* ── SVG canvas ── */
  #canvas {{ flex: 1; position: relative; }}
  svg {{ width: 100%; height: 100%; }}

  .link {{
    stroke: #3d4466;
    stroke-opacity: 0.7;
    stroke-width: 1.5px;
    marker-end: url(#arrow);
  }}
  .link.highlighted {{ stroke: #a78bfa; stroke-width: 2.5px; stroke-opacity: 1; }}

  .node circle {{
    stroke: #0f1117;
    stroke-width: 1.5px;
    cursor: pointer;
    transition: r 0.15s;
  }}
  .node circle:hover {{ stroke: #fff; stroke-width: 2px; }}
  .node.selected circle {{ stroke: #fff; stroke-width: 2.5px; }}

  .node-label {{
    font-size: 11px;
    fill: #cbd5e1;
    pointer-events: none;
    text-shadow: 0 0 4px #0f1117, 0 0 4px #0f1117;
  }}

  .edge-label {{
    font-size: 9px;
    fill: #64748b;
    pointer-events: none;
  }}

  /* ── Right panel ── */
  #panel {{
    width: 280px;
    background: #1a1d27;
    border-left: 1px solid #2d3048;
    overflow-y: auto;
    padding: 16px;
    flex-shrink: 0;
  }}
  #panel h2 {{ font-size: 13px; color: #a78bfa; margin-bottom: 12px; text-transform: uppercase; letter-spacing: .5px; }}
  #panel .placeholder {{ color: #475569; font-size: 12px; }}

  .entity-badge {{
    display: inline-block;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
    margin-bottom: 10px;
  }}
  .conn-row {{
    display: flex;
    gap: 6px;
    align-items: flex-start;
    margin-bottom: 6px;
    font-size: 12px;
    border-left: 2px solid #2d3048;
    padding-left: 8px;
  }}
  .rel-tag {{
    background: #2d3048;
    border-radius: 3px;
    padding: 1px 5px;
    font-size: 10px;
    color: #94a3b8;
    white-space: nowrap;
  }}
  .conn-name {{ color: #e2e8f0; }}
  .section-title {{ font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: .5px; margin: 12px 0 6px; }}

  /* ── Legend ── */
  #legend {{
    position: absolute;
    bottom: 16px;
    left: 16px;
    background: rgba(26,29,39,0.92);
    border: 1px solid #2d3048;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 11px;
  }}
  #legend h3 {{ color: #94a3b8; font-size: 10px; text-transform: uppercase; letter-spacing: .5px; margin-bottom: 8px; }}
  .leg-item {{ display: flex; align-items: center; gap: 7px; margin-bottom: 5px; color: #cbd5e1; }}
  .leg-dot {{ width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }}

  /* ── Search ── */
  #searchbox {{
    position: absolute;
    top: 14px;
    left: 14px;
  }}
  #search {{
    background: #1a1d27;
    border: 1px solid #2d3048;
    border-radius: 6px;
    color: #e0e0e0;
    padding: 6px 12px;
    font-size: 12px;
    width: 200px;
    outline: none;
  }}
  #search:focus {{ border-color: #a78bfa; }}
  #search::placeholder {{ color: #475569; }}
</style>
</head>
<body>

<div id="topbar">
  <h1>&#9900; DocuMind Knowledge Graph</h1>
  <span class="stat-pill">Entities: <b id="s-ent">-</b></span>
  <span class="stat-pill">Relations: <b id="s-rel">-</b></span>
  <span class="stat-pill">Showing: <b id="s-shown">-</b> nodes</span>
  <span class="stat-pill" style="margin-left:auto; color:#64748b; font-size:11px;">Click a node &nbsp;|&nbsp; Scroll to zoom &nbsp;|&nbsp; Drag to pan</span>
</div>

<div id="main">
  <div id="canvas">
    <div id="searchbox"><input id="search" type="text" placeholder="&#128269; Search entity..."></div>
    <div id="legend"></div>
  </div>
  <div id="panel">
    <h2>Entity Details</h2>
    <p class="placeholder">Click any node to see details and connections.</p>
  </div>
</div>

<script>
const RAW_NODES = {nodes_json};
const RAW_LINKS = {links_json};
const STATS     = {stats_json};

// ── Populate top-bar stats ──────────────────────────────────────────────────
document.getElementById('s-ent').textContent   = STATS.entity_count   ?? RAW_NODES.length;
document.getElementById('s-rel').textContent   = STATS.relation_count ?? RAW_LINKS.length;
document.getElementById('s-shown').textContent = RAW_NODES.length;

// ── Colour map ──────────────────────────────────────────────────────────────
const COLOR = {{
  Person:       '#818cf8',   // indigo
  Organization: '#f472b6',   // pink
  Location:     '#34d399',   // emerald
  Date:         '#fbbf24',   // amber
  Concept:      '#60a5fa',   // blue
  Product:      '#c084fc',   // purple
  Event:        '#fb923c',   // orange
  Other:        '#94a3b8',   // slate
  DocumentField:'#2dd4bf',   // teal
}};

const typeColor = t => COLOR[t] || COLOR.Other;

// ── Build legend ─────────────────────────────────────────────────────────────
const presentTypes = [...new Set(RAW_NODES.map(n => n.type))];
const legEl = document.getElementById('legend');
legEl.innerHTML = '<h3>Entity types</h3>' +
  presentTypes.map(t =>
    `<div class="leg-item"><div class="leg-dot" style="background:${{typeColor(t)}}"></div>${{t}}</div>`
  ).join('');

// ── SVG setup ────────────────────────────────────────────────────────────────
const canvas = document.getElementById('canvas');
const W = canvas.clientWidth, H = canvas.clientHeight;

const svg = d3.select('#canvas').append('svg');

// Arrow marker
svg.append('defs').append('marker')
   .attr('id','arrow').attr('viewBox','0 -4 8 8')
   .attr('refX',18).attr('refY',0)
   .attr('markerWidth',6).attr('markerHeight',6)
   .attr('orient','auto')
  .append('path').attr('d','M0,-4L8,0L0,4').attr('fill','#3d4466');

const zoomG = svg.append('g');

svg.call(d3.zoom().scaleExtent([0.15, 8])
   .on('zoom', e => zoomG.attr('transform', e.transform)));

// ── Simulation ───────────────────────────────────────────────────────────────
const nodes = RAW_NODES.map(d => ({{...d}}));
const links = RAW_LINKS.map(d => ({{...d}}));

const sim = d3.forceSimulation(nodes)
  .force('link',    d3.forceLink(links).id(d => d.id).distance(120).strength(0.6))
  .force('charge',  d3.forceManyBody().strength(-320))
  .force('center',  d3.forceCenter(W / 2, H / 2))
  .force('collide', d3.forceCollide().radius(d => (d.size || 8) + 14));

// ── Draw links ────────────────────────────────────────────────────────────────
const linkSel = zoomG.append('g').attr('class','links')
  .selectAll('line').data(links).enter().append('line').attr('class','link');

// Edge labels (shown at midpoint)
const edgeLabelSel = zoomG.append('g').attr('class','edge-labels')
  .selectAll('text').data(links).enter().append('text')
  .attr('class','edge-label')
  .text(d => d.type || '');

// ── Draw nodes ────────────────────────────────────────────────────────────────
const nodeSel = zoomG.append('g').attr('class','nodes')
  .selectAll('g').data(nodes).enter().append('g')
  .attr('class','node')
  .call(d3.drag()
    .on('start', (e,d) => {{ if(!e.active) sim.alphaTarget(0.3).restart(); d.fx=d.x; d.fy=d.y; }})
    .on('drag',  (e,d) => {{ d.fx=e.x; d.fy=e.y; }})
    .on('end',   (e,d) => {{ if(!e.active) sim.alphaTarget(0); d.fx=null; d.fy=null; }}))
  .on('click', onNodeClick);

nodeSel.append('circle')
  .attr('r',    d => d.size || 8)
  .attr('fill', d => typeColor(d.type));

nodeSel.append('text')
  .attr('class','node-label')
  .attr('x', d => (d.size || 8) + 5)
  .attr('y', 4)
  .text(d => d.name.length > 22 ? d.name.slice(0,20)+'…' : d.name);

// ── Tick ─────────────────────────────────────────────────────────────────────
sim.on('tick', () => {{
  linkSel
    .attr('x1', d => d.source.x).attr('y1', d => d.source.y)
    .attr('x2', d => d.target.x).attr('y2', d => d.target.y);

  edgeLabelSel
    .attr('x', d => (d.source.x + d.target.x) / 2)
    .attr('y', d => (d.source.y + d.target.y) / 2);

  nodeSel.attr('transform', d => `translate(${{d.x}},${{d.y}})`);
}});

// ── Node click — populate right panel ────────────────────────────────────────
function onNodeClick(event, d) {{
  event.stopPropagation();

  // Highlight selection
  nodeSel.classed('selected', n => n.id === d.id);

  // Highlight connected edges
  linkSel.classed('highlighted', l =>
    l.source.id === d.id || l.target.id === d.id);

  // Find connections
  const outgoing = links.filter(l => l.source.id === d.id);
  const incoming = links.filter(l => l.target.id === d.id);

  const nodeById = id => nodes.find(n => n.id === id) || {{}};

  const panel = document.getElementById('panel');
  panel.innerHTML = `
    <h2>Entity Details</h2>
    <div class="entity-badge" style="background:${{typeColor(d.type)}}22; color:${{typeColor(d.type)}}; border:1px solid ${{typeColor(d.type)}}44">
      ${{d.type}}
    </div>
    <div style="font-size:15px; font-weight:600; color:#f1f5f9; margin-bottom:14px; word-break:break-word;">${{d.name}}</div>

    ${{outgoing.length ? `
    <div class="section-title">&#8594; Outgoing (${{outgoing.length}})</div>
    ${{outgoing.map(l => `
      <div class="conn-row">
        <span class="rel-tag">${{l.type}}</span>
        <span class="conn-name">${{nodeById(l.target.id).name || l.target.id}}</span>
      </div>`).join('')}}` : ''}}

    ${{incoming.length ? `
    <div class="section-title">&#8592; Incoming (${{incoming.length}})</div>
    ${{incoming.map(l => `
      <div class="conn-row">
        <span class="rel-tag">${{l.type}}</span>
        <span class="conn-name">${{nodeById(l.source.id).name || l.source.id}}</span>
      </div>`).join('')}}` : ''}}

    ${{!outgoing.length && !incoming.length ? `
    <div class="section-title">No connections</div>
    <p style="font-size:12px;color:#475569">This entity has no relations yet.
    Upload more documents or run POST /kg/build to rebuild.</p>` : ''}}
  `;
}}

// Clear on background click
svg.on('click', () => {{
  nodeSel.classed('selected', false);
  linkSel.classed('highlighted', false);
  document.getElementById('panel').innerHTML =
    '<h2>Entity Details</h2><p class="placeholder">Click any node to see details and connections.</p>';
}});

// ── Search ────────────────────────────────────────────────────────────────────
document.getElementById('search').addEventListener('input', function() {{
  const q = this.value.toLowerCase().trim();
  if (!q) {{
    nodeSel.style('opacity', 1);
    linkSel.style('opacity', 0.7);
    edgeLabelSel.style('opacity', 1);
    return;
  }}
  const matchIds = new Set(nodes.filter(n => n.name.toLowerCase().includes(q)).map(n => n.id));
  nodeSel.style('opacity',      d => matchIds.has(d.id) ? 1 : 0.1);
  linkSel.style('opacity',      l => matchIds.has(l.source.id) || matchIds.has(l.target.id) ? 0.9 : 0.05);
  edgeLabelSel.style('opacity', l => matchIds.has(l.source.id) || matchIds.has(l.target.id) ? 1 : 0);

  if (matchIds.size === 1) {{
    const hit = nodes.find(n => matchIds.has(n.id));
    if (hit) onNodeClick({{ stopPropagation:()=>{{}} }}, hit);
  }}
}});
</script>
</body>
</html>"""
                return HTMLResponse(content=html)
            except Exception as e:
                logger.error(f"KG visualize failed: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to generate visualisation: {str(e)}",
                )
