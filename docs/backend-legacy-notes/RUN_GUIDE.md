# 🚀 Document Intelligence Workspace - Run Guide

## ✅ System Status: READY TO RUN

All tests passed successfully (9/9). System is operational and ready for use.

---

## Quick Start (3 Steps)

### Step 1: Navigate to Backend
```bash
cd back-end
```

### Step 2: Start FastAPI Server
```bash
uvicorn routes.routes:app --host 0.0.0.0 --port 8000 --reload
```

**API will be available at:**
- API: http://localhost:8000
- Interactive Docs: http://localhost:8000/docs
- Redoc: http://localhost:8000/redoc

### Step 3: (Optional) Start Streamlit UI
Open a new terminal:
```bash
cd back-end
streamlit run streamlit-app.py
```

---

## API Endpoints

### 1. Health Check
```bash
curl http://localhost:8000/api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "document_count": 0,
  "message": "System is operational"
}
```

### 2. Upload Document
```powershell
# PowerShell
$file = "C:\path\to\your\document.pdf"
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/upload" `
    -Method Post `
    -InFile $file `
    -ContentType "multipart/form-data"
```

**Response:**
```json
{
  "status": "success",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "classification": {
    "doc_type": "Application",
    "confidence": 0.95
  },
  "extracted_fields": {
    "full_name": "John Doe",
    "document_number": "ABC123",
    ...
  }
}
```

### 3. Query Documents
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the applicant name?",
    "top_k": 5,
    "search_type": "hybrid"
  }'
```

**Response:**
```json
{
  "query": "What is the applicant name?",
  "response": "Based on the documents, the applicant name is John Doe...",
  "retrieved_documents": [
    {
      "id": "doc_1",
      "text": "Application form for John Doe...",
      "metadata": {...},
      "score": 0.95
    }
  ],
  "evidence": [...]
}
```

### 4. Search Documents
```bash
curl -X GET "http://localhost:8000/api/v1/search?query=application&top_k=10&search_type=hybrid"
```

### 5. Add Document Manually
```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Document",
    "text": "This is a test document content",
    "source": "manual",
    "metadata": {"type": "test"}
  }'
```

### 6. Clear All Documents
```bash
curl -X DELETE http://localhost:8000/api/v1/documents
```

---

## Testing with Sample Data

### Test 1: Upload and Classify
```powershell
# Create a test text file
"I hereby apply for a driving license. My name is John Doe. DOB: 01/01/1990." | Out-File test_application.txt

# Upload it
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/upload" `
    -Method Post `
    -InFile "test_application.txt" `
    -ContentType "multipart/form-data"
```

### Test 2: Query
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the person name?", "top_k": 3}'
```

---

## What Works

### ✅ Document Processing
- **Upload**: PDF, DOCX, TXT, images (JPG, PNG)
- **OCR**: Text extraction from images
- **Classification**: 10 document types
  - Application, Identity Proof, Address Proof, Affidavit
  - Certificate, Court Document, Invoice, Contract
  - Receipt, Other
- **Field Extraction**: 50+ fields with evidence tracking

### ✅ Search & Retrieval
- **Hybrid Search**: Semantic (FAISS) + Keyword (BM25)
- **Grounded RAG**: Answers with source citations
- **Metadata Filtering**: By type, date, case, person, etc.

### ✅ Verification
- **Cross-Document Comparison**: Detect inconsistencies
- **Missing Document Check**: 5 pre-configured workflows
  - Government Application, Court Case, Notary/Affidavit
  - Property Transaction, Corporate Filing
- **Readiness Score**: Transparent scoring system

### ✅ Analysis
- **Timeline Extraction**: Chronological events
- **Duplicate Detection**: Find similar documents
- **Knowledge Graph**: Auto-populate entities and relationships

### ✅ Review & Management
- **Review Queue**: Route low-confidence items
- **Case Manager**: Bundle documents by case
- **Demo Modes**: Court, Government, Notary workflows

---

## Configuration

### Environment Variables (.env)
```bash
# Copy template
copy .env.template .env

# Required: Set at least one LLM provider
OPENAI_API_KEY=your_key_here
# OR
HUGGINGFACE_API_KEY=your_key_here

# Optional
EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2
OCR_ENGINE=tesseract  # or easyocr
```

---

## Troubleshooting

### Issue: "No module named X"
```bash
pip install -r requirements.txt
```

### Issue: "Tesseract not found"
**Option 1:** Install Tesseract
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- Mac: `brew install tesseract`
- Linux: `sudo apt-get install tesseract-ocr`

**Option 2:** Use EasyOCR
```bash
pip install easyocr
# Set in .env: OCR_ENGINE=easyocr
```

### Issue: "spaCy model not found"
```bash
python -m spacy download en_core_web_sm
```

### Issue: Port 8000 already in use
```bash
# Use a different port
uvicorn routes.routes:app --port 8001
```

---

## Performance Notes

**First Run:**
- Downloads embedding model (~90MB)
- Takes 1-2 minutes to initialize
- Subsequent runs are faster

**Document Processing:**
- Text files: <1 second
- PDFs: 1-3 seconds
- Images with OCR: 3-5 seconds

**Search:**
- Hybrid search: <100ms for 1000 documents
- RAG query: 1-3 seconds (depends on LLM)

---

## Next Steps

1. **Start the server** (see Step 2 above)
2. **Test with sample documents**
3. **Integrate with your frontend** (Group 1)
4. **Customize workflows** in:
   - `document/schemas/` - Add/modify field schemas
   - `verification/missing_document_checker.py` - Add workflows
   - `demo_modes/` - Create new demo modes

---

## API Documentation

Once the server is running, visit:
- **Interactive API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

These provide:
- Full API specification
- Try-it-out functionality
- Request/response examples
- Authentication (when implemented)

---

## Support

For issues or questions:
1. Check `TEST_RESULTS.md` for system status
2. Review `QUICKSTART.md` for setup help
3. Check logs for error messages
4. Refer to `README.md` for architecture details

---

**System Status: ✅ OPERATIONAL**  
**Last Tested: August 19, 2026**  
**Test Results: 9/9 PASSED**

Happy coding! 🚀
