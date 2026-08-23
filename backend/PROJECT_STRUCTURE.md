# Project Structure — DocuMind AI Unified Backend

Generated: 2026-08-22  
Source: merged-backend (DocuMind AI + SIH Phase-1 merge)

---

## Top-Level Layout

```
merged-backend/
├── main.py                      # FastAPI application entry point
├── config.py                    # Legacy flat config (env-var reading)
├── config.toml                  # Streamlit-only theme / server config
├── requirements.txt             # Pinned Python dependencies
├── .env.example                 # Environment variable template
├── .env.template                # Alternate env template (legacy)
├── .gitignore
│
├── core/                        # [NEW] Foundation layer (Phase-1 hardening)
│   ├── __init__.py
│   ├── logging.py               # Centralised structured logging
│   ├── middleware.py            # RequestID + exception middleware
│   ├── config.py                # Pydantic-Settings multi-env config
│   └── diagnostics.py          # Startup diagnostics runner
│
├── routes/
│   └── routes.py                # All FastAPI route registrations (RAGAPIRouter)
│
├── document/
│   ├── processor.py             # PDF/DOCX/TXT text extraction + chunking
│   ├── ocr_processor.py         # Enhanced OCR (Tesseract + EasyOCR + OpenCV)
│   ├── document_classifier.py   # Embedding-based classifier (8-10 types)
│   ├── field_extractor.py       # Schema + regex field extraction
│   ├── evidence_tracker.py      # Evidence chain per extracted field
│   ├── evidence.py              # Evidence dataclass
│   ├── document_status.py       # Document status enums / helpers
│   ├── ingestion.py             # Ingestion pipeline orchestration
│   ├── classifier.py            # ⚠ DUPLICATE — older classifier (superseded)
│   ├── schemas/                 # JSON schemas per document type
│   │   ├── document_types.py
│   │   ├── identity_proof.json
│   │   ├── address_proof.json
│   │   ├── application.json
│   │   ├── affidavit.json
│   │   ├── certificate.json
│   │   ├── contract.json
│   │   ├── court_document.json
│   │   ├── invoice.json
│   │   ├── receipt.json
│   │   └── other.json
│   └── __init__.py
│
├── rag/
│   ├── engine.py                # RAGEngine — retrieve + generate
│   ├── template_selector.py     # Dynamic prompt template selection
│   ├── grounded_rag.py          # Grounded / citation-aware RAG variant
│   └── __init__.py
│
├── embedding/
│   ├── model.py                 # SentenceTransformer + HuggingFace backends
│   └── __init__.py
│
├── storage/
│   ├── vector_db.py             # FaissVectorDatabase + KeywordVectorDatabase
│   ├── firebase_client.py       # Firebase Firestore + Storage client
│   └── __init__.py (assumed)
│
├── llm/
│   ├── model.py                 # BaseLLM, OpenAIModel, LocalLLM, ChainOfThoughtLLM
│   │                            # ⚠ also contains duplicate ServerlessLLM / HuggingFaceInferenceAPI
│   ├── ollama_model.py          # OllamaLLM — local Ollama server
│   ├── serverless_model.py      # ServerlessLLM, HuggingFaceInferenceAPI (canonical)
│   └── __init__.py
│
├── knowledge_graph/
│   ├── extractor.py             # KnowledgeGraphExtractor, EnhancedKnowledgeGraph
│   ├── kg_manager.py            # KGManager singleton (persistence, API surface)
│   ├── intelligence.py          # 8 intelligence engines (Provenance, CrossDoc, …)
│   ├── model.py                 # KG entity / relation dataclasses
│   ├── integration.py           # KG ↔ RAG integration helpers
│   ├── auto_populator.py        # Auto-populate KG from documents
│   ├── query.py                 # KG query helpers
│   ├── config.py                # KG-specific config
│   ├── neo4j_store.py           # Neo4j persistence backend (optional)
│   ├── neo4j_integration.py     # Neo4j integration helpers
│   ├── summarizer.py            # KG-based summarisation
│   ├── visualize.py             # KG visualisation helpers
│   ├── streamlit_ui.py          # Streamlit KG explorer UI
│   ├── kg_readme.txt            # KG module notes
│   └── __init__.py
│
├── analysis/
│   ├── duplicate_detector.py    # Embedding-based duplicate + version detection
│   ├── timeline_extractor.py    # Date/event timeline extraction
│   └── __init__.py
│
├── search/
│   ├── hybrid_search.py         # BM25 keyword + FAISS semantic + metadata filter
│   └── __init__.py
│
├── verification/
│   ├── document_comparison.py   # Field-level document comparison
│   ├── missing_document_checker.py # Workflow completeness checker
│   ├── readiness_score.py       # Submission readiness scorer
│   └── __init__.py
│
├── case/
│   ├── case_manager.py          # Case entity management
│   └── __init__.py
│
├── review/
│   ├── review_queue.py          # Document review queue
│   └── __init__.py
│
├── demo_modes/
│   ├── court_intelligence.py    # Court use-case demo
│   ├── government_verification.py
│   ├── notary_assistant.py
│   └── __init__.py
│
├── ui/                          # Streamlit UI components
├── test/                        # Test scripts
│
├── streamlit-app.py             # Main Streamlit UI entry
├── streamlit_kg_integration.py  # Streamlit + KG integration
├── improved_chunking.py         # Standalone chunking experiments
├── linecode.py                  # Utility / line code helpers
│
└── [Test images]                # 01_gov_id_clean.png … test5.png
```

---

## Module Dependency Graph (simplified)

```
main.py
  └─► routes/routes.py
        ├─► document/ocr_processor.py        ← requires: pytesseract, opencv-python
        ├─► document/document_classifier.py  ← requires: embedding/model.py
        ├─► document/field_extractor.py      ← requires: document/schemas/
        ├─► rag/engine.py
        │     ├─► embedding/model.py         ← requires: sentence-transformers
        │     ├─► storage/vector_db.py       ← requires: faiss-cpu
        │     └─► llm/ (Ollama / HF / Local)
        ├─► knowledge_graph/kg_manager.py
        │     └─► knowledge_graph/extractor.py  ← requires: spacy, networkx
        ├─► knowledge_graph/intelligence.py  ← requires: rapidfuzz
        └─► storage/firebase_client.py       ← requires: firebase-admin
```

---

## Known Issues (from inspection)

| # | File | Issue | Severity |
|---|------|--------|----------|
| 1 | `document/classifier.py` | Duplicate of document_classifier.py — older, incomplete version | Medium |
| 2 | `llm/model.py` | Contains duplicate `ServerlessLLM` + `HuggingFaceInferenceAPI` also in serverless_model.py | Medium |
| 3 | `document/processor.py` | `self.is_summary_mode` referenced but attribute is `self.is_summary_task` | High |
| 4 | `knowledge_graph/extractor.py` | `statistics()` method accesses `entity.type` on a dict (should be `entity['type']`) | Low |
| 5 | `routes/routes.py` | Partially written — ends mid-function (from interrupted write) | **Critical** |
| 6 | `embedding/model.py` | `from config import …` at module level risks circular import | Medium |
| 7 | `main.py` | Bare `except:` blocks swallow all errors silently | High |
| 8 | `.env.example` | Only Firebase vars documented — 30+ other vars missing | High |

---

## Entry Points

| Purpose | Command |
|---------|---------|
| API server (dev) | `uvicorn main:app --reload --port 8000` |
| API server (prod) | `uvicorn main:app --workers 4 --port 8000` |
| Streamlit UI | `streamlit run streamlit-app.py` |
| Start script | `.\start_server.bat` |
