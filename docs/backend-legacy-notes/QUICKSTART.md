# 🚀 Quick Start Guide

## Step 1: Install Dependencies

```bash
cd back-end

# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

## Step 2: Configure Environment

```bash
# Copy environment template
copy .env.template .env

# Edit .env file with your settings
# At minimum, set:
# - OPENAI_API_KEY (if using OpenAI)
# - HUGGINGFACE_API_KEY (if using HuggingFace)
```

## Step 3: Run System Tests

```bash
# Test all modules
python test_system.py
```

Expected output:
```
=========================================================================
TEST SUMMARY
=========================================================================
✓ PASS: Module Imports
✓ PASS: Document Classification
✓ PASS: OCR Processor
✓ PASS: Hybrid Search
✓ PASS: Verification Modules
✓ PASS: Case Manager
✓ PASS: Review Queue
✓ PASS: Knowledge Graph
✓ PASS: Demo Modes

TOTAL: 9/9 tests passed
=========================================================================

🎉 ALL TESTS PASSED! System is ready.
```

## Step 4: Start the API Server

```bash
# Start FastAPI backend
uvicorn routes.routes:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at: http://localhost:8000

## Step 5: Start Streamlit UI (Optional)

Open a new terminal:

```bash
cd back-end
venv\Scripts\activate  # Activate venv if using

# Start Streamlit
streamlit run streamlit-app.py
```

The UI will open in your browser automatically.

## Step 6: Test API Endpoints

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### Upload a Document (using PowerShell)
```powershell
$response = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/upload" `
    -Method Post `
    -InFile "path\to\your\document.pdf" `
    -ContentType "multipart/form-data"

$response.Content | ConvertFrom-Json
```

### Query Documents
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the applicant name?", "top_k": 5}'
```

## Troubleshooting

### Issue: ModuleNotFoundError
**Solution**: Make sure you've installed all dependencies:
```bash
pip install -r requirements.txt
```

### Issue: Tesseract not found
**Solution**: 
- Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
- Mac: `brew install tesseract`
- Linux: `sudo apt-get install tesseract-ocr`

Or use EasyOCR instead by setting `OCR_ENGINE=easyocr` in .env

### Issue: spaCy model not found
**Solution**:
```bash
python -m spacy download en_core_web_sm
```

### Issue: Firebase errors
**Solution**: 
- Make sure `firebase-credentials.json` exists
- Update `FIREBASE_CREDENTIALS_PATH` in .env

## What's Working

✅ **Document Processing**: Upload PDF, images, DOCX, TXT  
✅ **Classification**: 10 document types  
✅ **Field Extraction**: 50+ fields with evidence  
✅ **Hybrid Search**: Semantic + keyword  
✅ **Grounded RAG**: Answers with source citations  
✅ **Verification**: Cross-doc comparison, missing docs  
✅ **Case Management**: Bundle documents  
✅ **Review Queue**: Route low-confidence items  
✅ **Timeline**: Extract dates chronologically  
✅ **Duplicates**: Detect similar documents  
✅ **Knowledge Graph**: Auto-populate entities  

## Next Steps

1. **Upload test documents** through the API or UI
2. **Try different workflows**:
   - Government Application Verification
   - Court Case Analysis
   - Notary/Affidavit Processing
3. **Explore the API** at http://localhost:8000/docs (FastAPI auto-docs)
4. **Customize schemas** in `document/schemas/` for your needs
5. **Add workflows** in missing document checker

## Need Help?

- Check `README.md` for detailed documentation
- Review `test_system.py` for usage examples
- Check API docs at http://localhost:8000/docs

## System Architecture

```
User → FastAPI (/api/v1/*) → Processing Pipeline → Storage
         ↓                         ↓
    Streamlit UI            (Ingestion, Classification,
                            Extraction, Verification,
                            RAG, KG, Review Queue)
```

**Status**: ✅ Ready for Testing | 🎯 15/19 Features Complete (78.9%)
