# OCR Testing Guide

## 🎯 What is OCR?

OCR (Optical Character Recognition) extracts text from images. Your system supports:
- **Images**: JPG, JPEG, PNG, BMP, TIFF
- **PDFs**: With embedded images
- **Documents**: Scanned documents, photos of documents

---

## 🧪 Test Methods

### Method 1: Use the Generated Test Image ✅

**Image created**: `test_document.png` (in back-end folder)

**Steps:**
1. Go to http://localhost:8000/docs
2. Find **POST /upload**
3. Click "Try it out"
4. Click "Choose File"
5. Select `test_document.png`
6. Click "Execute"

**Expected Response:**
```json
{
  "status": "success",
  "message": "Processed document into X chunks",
  "document_type": "application",
  "extracted_fields": {
    "name": "Jane Smith",
    "date_of_birth": "15/03/1995",
    ...
  }
}
```

---

### Method 2: Use Your Phone to Create a Test Image 📱

**Steps:**
1. Write text on paper:
   ```
   Name: John Doe
   ID: 12345
   Date: 18/08/2026
   ```
2. Take a clear photo with your phone
3. Transfer photo to your computer
4. Upload at http://localhost:8000/docs

---

### Method 3: Use Online Sample Documents 🌐

Download sample documents from:
- **Sample IDs**: https://www.fakenamegenerator.com/
- **Sample Forms**: Search "sample application form PDF"
- **Government Forms**: Download any government form with text

---

## 🔍 How OCR Works in Your System

### Workflow:

```
Image Upload
    ↓
OCR Processing (Tesseract/EasyOCR)
    ↓
Text Extraction
    ↓
Document Classification
    ↓
Field Extraction
    ↓
Vector Embedding
    ↓
Ready for Query!
```

### Supported Operations:

1. **Upload Image** → OCR extracts text
2. **Classify Document** → Identifies document type
3. **Extract Fields** → Pulls out name, date, ID, etc.
4. **Query** → Ask questions about the image content

---

## 🧪 Test Queries After OCR Upload

After uploading an image, try these queries:

**Query 1: Extract Name**
```json
{
  "query": "What is the name?",
  "top_k": 3
}
```

**Query 2: Extract Date**
```json
{
  "query": "What is the date?",
  "top_k": 3
}
```

**Query 3: Get Summary**
```json
{
  "query": "Summarize this document",
  "top_k": 5
}
```

**Query 4: Specific Field**
```json
{
  "query": "What is the application type?",
  "top_k": 3
}
```

---

## 🐛 Troubleshooting OCR

### Issue: "OCR failed" or "No text extracted"

**Solutions:**
1. **Check image quality** - Use clear, high-contrast images
2. **Check image size** - Not too small (min 800x600 recommended)
3. **Check text visibility** - Text should be clear and readable
4. **Install Tesseract** - OCR engine must be installed

### Install Tesseract (if not installed):

**Windows:**
```powershell
# Download from: https://github.com/UB-Mannheim/tesseract/wiki
# Or use Chocolatey:
choco install tesseract
```

**Check if Tesseract is installed:**
```bash
tesseract --version
```

---

## 📊 OCR Quality Tips

### ✅ Good Images:
- Clear text
- High contrast (black text on white)
- Straight orientation
- Good lighting
- High resolution (at least 300 DPI)

### ❌ Avoid:
- Blurry images
- Low contrast
- Rotated text
- Poor lighting
- Very small text

---

## 🎯 Example Test Scenarios

### Scenario 1: License Application
```
Upload: Image of license form
Expected: Extract name, DOB, address, license type
Query: "What type of license is this?"
```

### Scenario 2: ID Card
```
Upload: Photo of ID card
Expected: Extract name, ID number, date
Query: "What is the ID number?"
```

### Scenario 3: Invoice
```
Upload: Invoice image
Expected: Extract date, amount, vendor
Query: "What is the total amount?"
```

---

## 📝 Quick Test Checklist

- [ ] Server running (`python main.py`)
- [ ] Test image created (`test_document.png` exists)
- [ ] Upload image at http://localhost:8000/docs
- [ ] Check response for extracted text
- [ ] Try query endpoint with questions
- [ ] Verify OCR accuracy in response

---

## 🚀 Next Steps

After successful OCR test:
1. **Test with real documents** - Upload actual forms/IDs
2. **Test different formats** - Try JPG, PNG, PDF
3. **Test field extraction** - Check if fields are correctly identified
4. **Test queries** - Ask various questions about the content
5. **Check evidence tracking** - Verify source citations

---

## 📞 Need Help?

If OCR isn't working:
1. Check server logs for errors
2. Verify Tesseract is installed
3. Try with a clearer image
4. Check image file format (should be JPG/PNG)
5. Ensure image file size < 10MB

---

**Ready to test! Use `test_document.png` at http://localhost:8000/docs** 🎉
