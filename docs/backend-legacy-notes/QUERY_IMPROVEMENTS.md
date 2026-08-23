# Query Response Improvements

## Issues Identified:

### 1. Field Extraction Returns Null Values ❌
**Problem**: Even though OCR extracted the text correctly, field extraction returns `null` for all fields.

**Text Extracted**:
```
APPLICATION FOR DRIVING LICENSE 
Name: Jane Smith 
Date of Birth: 15/03/1995 
Address: 123 Main Street, New York 
License Type: Class B 
Application Date: 18/08/2026
```

**Fields Expected** but got `null`:
- applicant_name → should be "Jane Smith"
- date_filed → should be "18/08/2026"  
- applicant_address → should be "123 Main Street, New York"

**Root Cause**: The LLM in field_extractor.py isn't properly parsing the text to extract structured fields.

---

### 2. Query Errors on Some Questions ❌
**Problem**: Query "What type of license?" returns:
```json
{
  "response": "I encountered an error while processing your question."
}
```

**Root Cause**: The LLM's answer generation is failing on certain question patterns.

---

## Solutions Applied:

### ✅ Fix 1: Improved "What Type Of" Question Handling

Updated `back-end/llm/model.py` `_generate_answer()` method to:
- Handle "what type of X?" questions specifically
- Look for "Class B" style license types
- Use regex patterns to find type information

### ⚠️ Fix 2 Needed: Field Extractor

The field extractor (`back-end/document/field_extractor.py`) needs improvement to:
1. Better parse key-value pairs like "Name: Jane Smith"
2. Handle date formats
3. Extract addresses properly

---

## Testing After Restart:

### Test 1: Restart Server
```bash
# Ctrl+C, then:
python main.py
```

### Test 2: Upload Again
Upload `test_document.png` at http://localhost:8000/docs

### Test 3: Try These Queries

**Query 1**: "What type of license?"
```json
{"query": "What type of license?", "top_k": 3}
```
**Expected**: "The license type is Class B."

**Query 2**: "What is the license type?"
```json
{"query": "What is the license type?", "top_k": 3}
```
**Expected**: "The license type is Class B."

**Query 3**: "Who is the applicant?"
```json
{"query": "Who is the applicant?", "top_k": 3}
```
**Expected**: "The applicant is Jane Smith."

---

## Known Limitations:

1. **Field Extraction**: Still returns null - needs LLM improvement
2. **Complex Queries**: May still fail on very complex questions
3. **Response Length**: Sometimes returns more text than needed

---

## Next Steps if Issues Persist:

1. Check server terminal logs for Python errors
2. Look for stack traces when query fails
3. Share the error logs to debug further

---

## Alternative: Use Query Endpoint Instead of Field Extraction

Since field extraction isn't working well, you can use the query endpoint to get any information:

- ❌ Don't rely on: `extracted_fields` in upload response
- ✅ Do use: `POST /query` endpoint with natural language questions

**Example**:
```json
POST /query
{
  "query": "Extract all information from this document as a structured list"
}
```

This will use the RAG system which works better than the field extractor!
