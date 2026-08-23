# 📤 Document Upload & Testing Guide

## ✅ Your API is Ready!

Now you can upload documents and test all features!

---

## 🚀 Step 1: Start the Server

```bash
cd back-end
python main.py
```

Wait for:
```
✓ RAG engine initialized successfully
✓ API routes registered successfully
INFO: Uvicorn running on http://0.0.0.0:8000
```

---

## 📄 Step 2: Create a Test Document

**Create a simple text file:**

```powershell
# PowerShell
"I hereby apply for a driving license. 
My name is John Doe.
Date of Birth: January 1, 1990.
Address: 123 Main Street, Mumbai, Maharashtra.
Contact: +91-9876543210" | Out-File test_application.txt
```

---

## 📤 Step 3: Upload the Document

### Method 1: Using Browser (Easiest!)

1. Go to: **http://localhost:8000/docs**
2. Find **POST /upload**
3. Click **"Try it out"**
4. Click **"Choose File"** and select your `test_application.txt`
5. Click **"Execute"**

### Method 2: Using PowerShell

```powershell
$file = "test_application.txt"
$uri = "http://localhost:8000/upload"

# Create multipart form data
$multipartContent = [System.Net.Http.MultipartFormDataContent]::new()
$fileStream = [System.IO.File]::OpenRead($file)
$fileContent = [System.Net.Http.StreamContent]::new($fileStream)
$multipartContent.Add($fileContent, "file", [System.IO.Path]::GetFileName($file))

# Send request
$response = Invoke-RestMethod -Uri $uri -Method Post -Body $multipartContent -ContentType "multipart/form-data"
$response | ConvertTo-Json -Depth 10

$fileStream.Close()
```

### Method 3: Using Curl

```bash
curl -X POST "http://localhost:8000/upload" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@test_application.txt"
```

---

## ✅ Expected Response

```json
{
  "status": "success",
  "message": "Processed document into 1 chunks",
  "document_id": "550e8400-e29b-41d4-a716-446655440000",
  "document_type": "Application",
  "classification_confidence": 0.95,
  "extracted_fields": {
    "full_name": "John Doe",
    "date_of_birth": "1990-01-01",
    "address": "123 Main Street, Mumbai, Maharashtra",
    "contact_number": "+91-9876543210"
  },
  "chunk_count": 1,
  "document_ids": ["doc_001"],
  "processing_time_seconds": 2.5,
  "firebase_enabled": false
}
```

---

## 🔍 Step 4: Query Your Document

### Using Browser:
1. Go to: **http://localhost:8000/docs**
2. Find **POST /query**
3. Click **"Try it out"**
4. Enter query: `"What is the applicant's name?"`
5. Click **"Execute"**

### Using PowerShell:

```powershell
$body = @{
    query = "What is the applicant's name?"
    top_k = 5
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/query" `
    -Method Post `
    -Body $body `
    -ContentType "application/json" | ConvertTo-Json -Depth 10
```

### Expected Response:

```json
{
  "query": "What is the applicant's name?",
  "response": "The applicant's name is John Doe.",
  "retrieved_documents": [...],
  "search_type": "hybrid",
  "evidence": [
    {
      "source_document": "test_application.txt",
      "page": "unknown",
      "evidence_snippet": "My name is John Doe...",
      "confidence": 0.95
    }
  ]
}
```

---

## 🧪 Test Different Document Types

### 1. **Identity Proof** (Aadhaar)
```text
Aadhaar Card
Name: Priya Sharma
Aadhaar Number: 1234-5678-9012
Date of Birth: 15/03/1995
Address: Flat 402, Green Valley, Pune, Maharashtra
```

### 2. **Invoice**
```text
INVOICE
Invoice Number: INV-2024-001
Date: 18/08/2026
Bill To: Acme Corp
Amount: Rs. 50,000
Due Date: 30/08/2026
```

### 3. **Certificate**
```text
CERTIFICATE OF COMPLETION
This is to certify that Rahul Kumar
has successfully completed the course
"Advanced Python Programming"
Date: 15/08/2026
Grade: A+
```

---

## 📊 Available Endpoints

### Document Operations
- `POST /upload` - Upload and process document
- `POST /documents` - Add documents manually
- `GET /documents/{id}/status` - Check processing status
- `DELETE /documents` - Clear all documents

### Search & Query
- `POST /query` - RAG query with answer and citations
- `GET /search` - Search documents without generating answer

### System
- `GET /` - API information
- `GET /health` - Health check
- `GET /status` - Detailed status

---

## 🎯 What Happens When You Upload?

1. **Upload** - File received
2. **OCR** (if image) - Text extraction
3. **Classification** - Document type identified (10 types)
4. **Field Extraction** - 50+ fields extracted automatically
5. **Indexing** - Added to vector database
6. **Ready** - Can be queried immediately!

---

## 🔍 Classification Types

Your document will be classified into one of:
1. **Application** - Forms, applications
2. **Identity Proof** - Aadhaar, PAN, Passport
3. **Address Proof** - Utility bills, bank statements
4. **Affidavit** - Legal declarations
5. **Certificate** - Educational, professional
6. **Court Document** - Legal documents
7. **Invoice** - Bills, invoices
8. **Contract** - Agreements
9. **Receipt** - Payment receipts
10. **Other** - Miscellaneous

---

## 📈 Field Extraction

Automatically extracts:
- **Personal**: Names, DOB, contact info
- **Address**: Full address, PIN code
- **IDs**: Aadhaar, PAN, passport numbers
- **Financial**: Amounts, account numbers
- **Dates**: Issue dates, expiry dates
- **Legal**: Case numbers, court details
- **And 40+ more fields!**

---

## 💡 Pro Tips

1. **Supported Formats**: PDF, TXT, DOCX, JPG, PNG
2. **Max File Size**: Depends on your system RAM
3. **Processing Time**: 1-5 seconds per document
4. **Batch Upload**: Upload multiple files sequentially
5. **Evidence**: Every answer includes source citations
6. **Confidence**: Low confidence items (<70%) flagged for review

---

## 🐛 Troubleshooting

### "No text extracted"
- **Image files**: Install Tesseract OCR
- **PDF files**: Check if PDF contains text (not just images)
- **DOCX files**: Ensure proper formatting

### "Classification confidence low"
- Normal for ambiguous documents
- Still processes correctly
- Can be manually verified

### "Slow processing"
- First run downloads models (~90MB)
- Subsequent uploads are faster
- Large files take longer

---

## 📚 More Examples

Check the browser docs at: **http://localhost:8000/docs**

Every endpoint has:
- ✅ Try-it-out feature
- ✅ Example requests
- ✅ Response schemas
- ✅ Error codes

---

## 🎉 Success!

You can now:
- ✅ Upload any document
- ✅ Automatic classification
- ✅ Automatic field extraction
- ✅ Query with natural language
- ✅ Get answers with citations

**Start uploading at: http://localhost:8000/docs** 🚀
