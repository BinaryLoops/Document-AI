# API Endpoint List — DocuMind AI Unified Backend

Generated: 2026-08-22  
Base URL: `http://localhost:8000`  
Docs UI: `http://localhost:8000/docs`

---

## Core / System Endpoints (main.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | None | Root — API info + status |
| GET | `/health` | None | Health check (always available) |
| GET | `/status` | None | Detailed component status |
| GET | `/version` | None | **[NEW]** Version + build info |
| GET | `/readiness` | None | **[NEW]** Readiness probe (all components up?) |

---

## Document Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/documents` | None | Bulk-add documents via JSON body |
| POST | `/upload` | None | Upload 1-N files (PDF/TXT/DOCX/JPG/PNG) — OCR, classify, extract fields, index into FAISS, build KG |
| GET | `/documents/{document_id}/status` | None | Per-document Firebase processing status |
| DELETE | `/documents` | None | Clear all documents from FAISS index |

### POST /upload — Request
```
Content-Type: multipart/form-data
files[]        : UploadFile[]   (required) — one or more files
chunk_size     : int            (default 1000, 100–5000)
chunk_overlap  : int            (default 200, 0–500)
build_kg       : bool           (default true) — auto-populate KG
```

### POST /upload — Response (per file)
```json
{
  "status": "success",
  "filename": "identity.png",
  "document_id": "uuid",
  "document_type": "Identity Proof",
  "classification_confidence": 0.92,
  "extracted_fields": [...],
  "chunk_count": 3,
  "document_ids": [...],
  "processing_time_seconds": 1.4,
  "firebase_enabled": false,
  "knowledge_graph": { "entity_count": 7, ... }
}
```

### POST /documents — Request
```json
{
  "documents": [
    { "title": "string", "text": "string", "source": "string", "metadata": {} }
  ]
}
```

---

## Query / Search Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/query` | None | RAG query — retrieve + generate answer |
| GET | `/search` | None | Semantic/keyword/hybrid search (no generation) |

### POST /query — Request
```json
{
  "query": "string",
  "top_k": 5,
  "search_type": "hybrid",
  "filter_dict": null,
  "max_tokens": 512,
  "use_kg": false
}
```

### POST /query — Response
```json
{
  "query": "string",
  "response": "string",
  "retrieved_documents": [
    { "id": "uuid", "text": "...", "metadata": {}, "score": 0.87 }
  ],
  "search_type": "hybrid",
  "evidence": [
    { "source_document": "file.pdf", "page": "1", "evidence_snippet": "...", "confidence": 0.87 }
  ],
  "kg_context": null
}
```

### GET /search — Parameters
```
query       : string  (required)
top_k       : int     (1–20, default 5)
search_type : string  (semantic | keyword | hybrid)
```

---

## Knowledge Graph Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/kg/stats` | None | Entity/relation counts + type breakdowns |
| GET | `/kg/graph` | None | Nodes + links JSON for D3.js rendering |
| GET | `/kg/entity/{name}` | None | Look up entity by name (partial/case-insensitive) |
| POST | `/kg/build` | None | (Re)build KG from all FAISS-indexed documents |
| DELETE | `/kg` | None | Clear entire knowledge graph |
| GET | `/kg/visualize` | None | Interactive D3.js HTML visualisation |

### GET /kg/graph — Parameters
```
max_nodes : int (10–500, default 100)
```

### GET /kg/visualize — Parameters
```
max_nodes : int (10–300, default 80)
```

### POST /kg/build — Parameters
```
reset : bool (default false) — clear before rebuild
```

### GET /kg/entity/{name} — Response
```json
{
  "found": true,
  "name": "Ravi Kumar",
  "type": "Person",
  "confidence": 0.95,
  "connections": [...]
}
```

---

## Intelligence Endpoints (8 Engines)

All `POST`. Require intelligence engines to be available (503 otherwise).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/intelligence/provenance` | Evidence chain + source provenance for a RAG answer |
| POST | `/intelligence/cross-doc` | Shared entities / fields across multiple documents |
| POST | `/intelligence/completeness` | Missing required fields + workflow completeness |
| POST | `/intelligence/contradictions` | Field-level contradictions across documents |
| POST | `/intelligence/version` | Version / supersession detection between 2 docs |
| POST | `/intelligence/graphrag` | KG-guided retrieval + answer generation |
| POST | `/intelligence/compare` | Structured side-by-side field diff with scores |
| POST | `/intelligence/explain` | Step-by-step reasoning trace for an answer |

### POST /intelligence/provenance — Request
Uses `QueryInput` model (same as `/query`).

### POST /intelligence/cross-doc — Request
```json
[
  {
    "document_id": "abc",
    "filename": "id.png",
    "document_type": "Identity Proof",
    "extracted_fields": [{"field": "full_name", "value": "Ravi Kumar"}]
  }
]
```

### POST /intelligence/completeness — Request
```json
{
  "document_type": "Application",
  "extracted_fields": [...],
  "workflow": "GOVERNMENT_APPLICATION",
  "uploaded_document_types": ["Identity Proof", "Address Proof"]
}
```
Supported workflows: `GOVERNMENT_APPLICATION`, `COURT_CASE`, `NOTARY`, `KYC`

### POST /intelligence/version — Request
```json
{
  "document_a": { "document_id": "...", "extracted_fields": [...] },
  "document_b": { "document_id": "...", "extracted_fields": [...] }
}
```

### POST /intelligence/compare — Request
Same structure as `/intelligence/version`.

---

## Pydantic Models

### QueryInput
```json
{
  "query": "string (required)",
  "top_k": 5,
  "search_type": "hybrid",
  "filter_dict": null,
  "max_tokens": 512,
  "use_kg": false
}
```

### HealthResponse
```json
{
  "status": "healthy | unhealthy | degraded",
  "version": "1.0.0",
  "document_count": 0,
  "message": "string"
}
```

---

## HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 404 | Document / entity not found |
| 422 | Validation error (Pydantic) |
| 500 | Internal server error |
| 503 | Component not available (KG / Intelligence engines) |

---

## OpenAPI / Swagger

- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`
- OpenAPI JSON: `GET /openapi.json`

The `/upload` endpoint has a custom `openapi()` schema override that forces Swagger UI to render a proper multi-file picker rather than a text input field.
