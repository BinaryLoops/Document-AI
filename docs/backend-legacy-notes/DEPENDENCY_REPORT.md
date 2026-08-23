# Dependency Report — DocuMind AI Unified Backend

Generated: 2026-08-22

---

## Runtime Dependencies (`requirements.txt`)

### Core Framework
| Package | Version Constraint | Used By | Notes |
|---------|-------------------|---------|-------|
| fastapi | >=0.100.0 | main.py, routes/ | Upgraded from >=0.95.0 in merge |
| uvicorn | >=0.22.0 | main.py | ASGI server |
| pydantic | >=1.10.0 | routes/, core/config.py | V1 API used — V2 breaking changes |
| python-multipart | >=0.0.6 | routes/ (file upload) | Required for File() / UploadFile |
| python-dotenv | >=0.20.0 | config.py, main.py | .env loading |

### ML / Embeddings
| Package | Version Constraint | Used By | Notes |
|---------|-------------------|---------|-------|
| numpy | >=1.24.0 | everywhere | Core numerical ops |
| torch | >=2.0.0 | embedding/model.py | CPU inference only unless GPU set |
| sentence-transformers | >=2.2.2 | embedding/model.py | Default: all-MiniLM-L6-v2 (384-dim) |
| transformers | >=4.28.1 | embedding/model.py (HF backend) | Optional HF embedding backend |
| faiss-cpu | (no version pin) | storage/vector_db.py | ⚠ No version pin — should add ==1.7.4 |

### Document Processing
| Package | Version Constraint | Used By | Notes |
|---------|-------------------|---------|-------|
| PyPDF2 | >=3.0.0 | document/processor.py | Fallback PDF extractor |
| PyMuPDF | >=1.18.20 | document/processor.py | Primary PDF extractor (fitz) |
| pdfplumber | >=0.5.28 | (available, not directly imported in processor) |
| python-docx | >=0.8.11 | document/processor.py | DOCX extraction |
| Pillow | >=9.0.0 | routes/ (Image.open), ocr_processor.py | Image handling |

### OCR
| Package | Version Constraint | Used By | Notes |
|---------|-------------------|---------|-------|
| pytesseract | >=0.3.10 | document/ocr_processor.py | Tesseract wrapper — requires Tesseract binary |
| easyocr | >=1.7.0 | document/ocr_processor.py | GPU optional, heavy (downloads models on first use) |
| opencv-python | >=4.8.0 | document/ocr_processor.py | Enhanced preprocessing (Otsu, deskew) |

### Search & NLP
| Package | Version Constraint | Used By | Notes |
|---------|-------------------|---------|-------|
| rank-bm25 | >=0.2.2 | search/hybrid_search.py | BM25 keyword search |
| rapidfuzz | >=3.0.0 | knowledge_graph/intelligence.py | Fuzzy string matching |
| python-Levenshtein | >=0.21.0 | (available) | String distance |
| spacy | >=3.0.0 | knowledge_graph/extractor.py | NER + dependency parsing |

### Knowledge Graph
| Package | Version Constraint | Used By | Notes |
|---------|-------------------|---------|-------|
| networkx | >=2.5 | knowledge_graph/extractor.py | Graph algorithms |
| neo4j | >=5.0.0 | knowledge_graph/neo4j_store.py | Optional — only if NEO4J vars set |
| pyvis | >=0.3.2 | knowledge_graph/ | KG HTML visualisation |
| matplotlib | >=3.4.0 | knowledge_graph/ | Graph plotting |

### LLM / AI
| Package | Version Constraint | Used By | Notes |
|---------|-------------------|---------|-------|
| openai | >=1.0.0 | llm/model.py | OpenAI API client |
| requests | >=2.28.0 | llm/ollama_model.py, llm/serverless_model.py | HTTP to Ollama / HF |
| streamlit | >=1.22.0 | streamlit-app.py | UI only, not used by API |

### Firebase
| Package | Version Constraint | Used By | Notes |
|---------|-------------------|---------|-------|
| firebase-admin | >=6.0.0 | storage/firebase_client.py | Firestore + Storage |

### Utilities
| Package | Version Constraint | Used By | Notes |
|---------|-------------------|---------|-------|
| python-dateutil | >=2.8.2 | analysis/timeline_extractor.py | Date parsing |
| datefinder | >=0.7.3 | analysis/timeline_extractor.py | Date discovery |
| tqdm | >=4.65.0 | (available) | Progress bars |
| pyyaml | >=6.0 | (available) | YAML config parsing |

---

## External System Dependencies

| System | Required? | Configuration | Purpose |
|--------|-----------|--------------|---------|
| Tesseract OCR binary | Optional | `TESSERACT_CMD` or PATH | OCR for images |
| Ollama server | Optional (preferred) | `http://localhost:11434` | Local LLM inference |
| Firebase project | Optional | `FIREBASE_CREDENTIALS_PATH`, `FIREBASE_STORAGE_BUCKET` | Cloud storage + status tracking |
| Neo4j database | Optional | `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` | Graph persistence |
| HuggingFace API | Optional (LLM fallback) | `HUGGINGFACE_API_KEY` | Remote LLM inference |
| OpenAI API | Optional | `OPENAI_API_KEY` | GPT LLM |

---

## Issues Found

### Critical
| Issue | File | Details |
|-------|------|---------|
| `faiss-cpu` has no version pin | requirements.txt | Should be `faiss-cpu==1.7.4` — unpinned may break on newer numpy |
| `pydantic>=1.10.0` | requirements.txt | Pydantic V2 (>=2.0) has breaking changes; project uses V1 API — should pin `pydantic>=1.10.0,<2.0` |

### Medium
| Issue | File | Details |
|-------|------|---------|
| Duplicate class definitions | llm/model.py | `ServerlessLLM` and `HuggingFaceInferenceAPI` duplicated in llm/serverless_model.py |
| `easyocr` downloads on first use | requirements.txt | ~1GB model download on first OCR call — no warning to user |
| `spacy` model not auto-installed | knowledge_graph/extractor.py | `en_core_web_sm` must be downloaded separately: `python -m spacy download en_core_web_sm` |

### Low
| Issue | File | Details |
|-------|------|---------|
| `pdfplumber` listed but not imported in processor | requirements.txt | Dead dependency or planned use |
| `streamlit` in API requirements | requirements.txt | UI-only dep — should be in a separate extras group |

---

## Install Commands

```powershell
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Install spaCy English model (required for KG)
python -m spacy download en_core_web_sm

# 3. Install Tesseract OCR binary (Windows)
# Download: https://github.com/UB-Mannheim/tesseract/wiki
# Then set TESSERACT_CMD in .env

# 4. Install Ollama (optional local LLM)
# https://ollama.ai — then: ollama pull phi
```

---

## Python Version

Tested on: Python 3.10+  
Minimum: Python 3.9 (for `tuple[str, float]` type hint in ocr_processor.py — requires 3.10+)  
Recommendation: **Python 3.10 or 3.11**
