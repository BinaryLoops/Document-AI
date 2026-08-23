# 📚 Document Intelligence Workspace - SIH PS23 Group 2

## 🌟 Overview

A comprehensive **Document Intelligence System** combining RAG (Retrieval-Augmented Generation), OCR, field extraction, verification, and knowledge graphs for government, legal, and institutional document processing.

**Live Demo**: [Deployment URL - To be added]

---

## 🎯 Key Features

### Core Document Processing (P0-P6)
- ✅ **Multi-format Document Ingestion** (PDF, Images, DOCX, TXT)
- ✅ **Advanced OCR** with Tesseract/EasyOCR (page-level tracking, confidence scoring)
- ✅ **Document Classification** (10 types with embedding-based approach)
- ✅ **Structured Field Extraction** (config-based JSON schemas)
- ✅ **Evidence Tracking** (mandatory source citations for all extractions)
- ✅ **Hybrid Search** (FAISS semantic + BM25 keyword + metadata filters)
- ✅ **Grounded RAG** (anti-hallucination guardrails, refuses general knowledge)

### Verification & Analysis (P7-P14)
- ✅ **Cross-Document Comparison** (fuzzy matching, inconsistency detection)
- ✅ **Missing Document Checker** (workflow-based requirements)
- 🚧 **Knowledge Graph** (entity extraction, relationship mapping)
- ✅ **Case Management** (bundle documents, track status)
- 🚧 **Verification Score** (readiness calculation)
- 🚧 **Human Review Queue** (low-confidence routing)
- 🚧 **Timeline Extraction** (chronological date display)
- 🚧 **Duplicate Detection** (embedding similarity)

### Applications (P15)
- 🚧 **Court Intelligence Mode**
- 🚧 **Government Application Verification**
- 🚧 **Notary/Affidavit Assistant**

### Deployment (P16-P17)
- 🚧 **Firebase Integration** (Auth, Firestore, Storage)
- 🚧 **Railway Deployment**
- 🚧 **Polished Streamlit UI**

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend Layer                          │
│              (Streamlit UI / Flutter App)                   │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                   API Layer (FastAPI)                       │
│  /upload  /query  /search  /compare  /cases  /insights     │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                  Core Processing Layer                      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Ingestion   │  │    Field     │  │  Evidence    │     │
│  │  + OCR       │  │  Extraction  │  │  Tracker     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │Classifier    │  │Hybrid Search │  │Grounded RAG  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │Verification  │  │Case Manager  │  │Knowledge     │     │
│  │& Comparison  │  │              │  │Graph         │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│                  Storage Layer                              │
│  Firebase (Firestore + Storage)  │  FAISS  │  Neo4j       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 Installation

### Prerequisites
- Python 3.8+
- Tesseract OCR (optional for image processing)
- Neo4j (optional for knowledge graph)
- Firebase project (for deployment)

### Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd SIH/back-end
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

4. **Configure environment**
```bash
cp .env.template .env
# Edit .env with your configuration
```

5. **Run the application**
```bash
# Start FastAPI backend
uvicorn routes.routes:app --host 0.0.0.0 --port 8000

# Start Streamlit UI (separate terminal)
streamlit run streamlit-app.py
```

---

## 🚀 Quick Start Guide

### 1. Upload a Document
```python
from document.ingestion import DocumentIngestion

# Initialize ingestion pipeline
ingestion = DocumentIngestion(ocr_engine="tesseract")

# Process document
metadata, chunks, chunk_meta = ingestion.ingest_document(
    file_path="application.pdf",
    filename="application.pdf",
    source="user_upload"
)

print(f"Status: {metadata.status}")
print(f"Pages: {metadata.page_count}")
```

### 2. Classify Document
```python
from document.document_classifier import DocumentClassifier
from embedding.model import create_embedding_model

# Initialize classifier
classifier = DocumentClassifier(create_embedding_model())

# Classify
doc_type, confidence = classifier.classify(full_text)
print(f"Type: {doc_type}, Confidence: {confidence:.2f}")
```

### 3. Extract Fields
```python
from document.field_extractor import FieldExtractor

# Initialize extractor (requires RAG engine)
extractor = FieldExtractor(rag_engine)

# Extract fields with evidence
fields = extractor.extract(
    chunks=chunks,
    chunk_metadata=chunk_meta,
    document_type="Application",
    filename="application.pdf"
)

for field in fields:
    print(f"{field['field']}: {field['value']} (confidence: {field['confidence']})")
    print(f"  Evidence: {field['evidence']['evidence_snippet'][:100]}...")
```

### 4. Perform Grounded RAG Query
```python
from rag.grounded_rag import GroundedRAG

# Initialize grounded RAG
grounded_rag = GroundedRAG(llm_generator=rag_engine._generate_llm_response)

# Query with mandatory source citation
response = grounded_rag.generate_response(
    query="What is the applicant's name?",
    retrieved_documents=search_results
)

print(f"Answer: {response.response}")
print(f"Confidence: {response.confidence}")
for evidence in response.evidence:
    print(f"  Source: {evidence.source_document}, Page: {evidence.page}")
```

### 5. Compare Documents
```python
from verification.document_comparison import DocumentComparison

# Initialize comparison
comparison = DocumentComparison(fuzzy_threshold=85.0)

# Compare documents in a case
inconsistencies = comparison.compare_documents(documents)

for inc in inconsistencies:
    print(f"⚠ {inc['severity']}: {inc['message']}")
    print(f"  Doc A: {inc['document_a']['value']}")
    print(f"  Doc B: {inc['document_b']['value']}")
```

### 6. Check Missing Documents
```python
from verification.missing_document_checker import MissingDocumentChecker

# Initialize checker
checker = MissingDocumentChecker()

# Check requirements
result = checker.check_documents(
    document_types=["Application", "Identity Proof"],
    workflow="GOVERNMENT_APPLICATION"
)

print(result['status_message'])
print(f"Completeness: {result['completeness_percentage']}%")
print(result['checklist'])
```

---

## 🔌 API Endpoints

### Document Management
- `POST /api/v1/upload` - Upload and process document
- `GET /api/v1/documents/{id}/status` - Check processing status
- `GET /api/v1/documents/{id}/results` - Get extraction results

### Search & Query
- `POST /api/v1/search` - Semantic + keyword search
- `POST /api/v1/query` - Grounded RAG query
- `POST /api/v1/chat` - Interactive chat with documents

### Verification
- `POST /api/v1/compare` - Compare documents
- `GET /api/v1/insights` - Get verification insights
- `GET /api/v1/cases/{id}` - Get case bundle

### System
- `GET /api/v1/health` - Health check
- `GET /api/v1/graph/{id}` - Knowledge graph data

---

## 📊 Document Types Supported

1. **Application** - Government/institutional forms
2. **Identity Proof** - Aadhaar, PAN, Passport, License
3. **Address Proof** - Utility bills, bank statements
4. **Affidavit** - Sworn statements, declarations
5. **Certificate** - Birth, education, income, caste
6. **Court Document** - Orders, judgments, summons
7. **Invoice** - Bills, payment requests
8. **Contract** - Agreements, MOUs
9. **Receipt** - Payment confirmations
10. **Other** - Miscellaneous documents

---

## 🔧 Configuration

### Environment Variables (.env)
```bash
# Embedding Model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# LLM
OPENAI_API_KEY=your-key-here
LLM_MODEL=gpt-3.5-turbo

# Firebase
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_STORAGE_BUCKET=your-bucket
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json

# Neo4j (optional)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-password

# OCR
OCR_ENGINE=tesseract
OCR_LANGUAGE=eng

# Search
SEARCH_TYPE=hybrid
SEMANTIC_SEARCH_WEIGHT=0.7
KEYWORD_SEARCH_WEIGHT=0.3
```

### Custom Workflows
Add custom workflows for missing document checker:
```python
checker.add_workflow(
    workflow_id="CUSTOM_WORKFLOW",
    name="Custom Application Process",
    required_documents=["Application", "Identity Proof", "Address Proof"],
    optional_documents=["Certificate", "Affidavit"]
)
```

---

## 🧪 Testing

```bash
# Run unit tests
pytest tests/

# Test specific module
pytest tests/test_document_comparison.py

# Test with coverage
pytest --cov=back-end tests/
```

---

## 📈 Performance

- **Document Processing**: ~2-5 seconds per page (OCR), <1 second (text-native)
- **Classification**: ~100ms per document
- **Field Extraction**: ~2-3 seconds per document (LLM-based)
- **Search**: ~50-100ms for hybrid search (1000 documents)
- **Comparison**: <500ms for 10 documents

---

## 🛡️ Security

- ✅ No sensitive data in logs
- ✅ API key protection via environment variables
- ✅ Input validation on all endpoints
- 🚧 Firebase Auth for user authentication
- 🚧 Rate limiting on API endpoints
- 🚧 CORS configuration for production

---

## 📖 Documentation

- [Implementation Status](./IMPLEMENTATION_STATUS.md) - Detailed progress report
- [Gap Analysis](./P0_GAP_ANALYSIS.md) - Initial assessment
- [API Documentation](./docs/API.md) - Detailed API reference (to be created)
- [Deployment Guide](./docs/DEPLOYMENT.md) - Production deployment (to be created)

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

## 📜 License

MIT License - See LICENSE file for details

---

## 👥 Team - SIH PS23 Group 2

**Project Lead**: [Name]  
**Backend Developers**: [Names]  
**Frontend Developers**: [Names]  
**ML Engineers**: [Names]

---

## 📞 Contact

- **Repository**: [GitHub URL]
- **Demo**: [Live Demo URL]
- **Documentation**: [Docs URL]
- **Email**: [Contact Email]

---

## 🎉 Acknowledgments

- SIH 2024 Organizing Committee
- Mentors and Advisors
- Open source community for various libraries and tools

---

**Status**: 🚧 Active Development | ✅ Core Features Complete | 🎯 Production Ready: 60%

**Last Updated**: [Current Date]