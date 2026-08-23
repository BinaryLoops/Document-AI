# Security Gap Report — DocuMind AI Unified Backend

Generated: 2026-08-22  
Severity: CRITICAL / HIGH / MEDIUM / LOW

---

## CRITICAL

### C1 — CORS wildcard in production
**File:** `main.py` line 27  
**Code:** `allow_origins=["*"]`  
**Risk:** Any website can make authenticated cross-origin requests to the API.  
**Fix:** Replace with explicit origin list in production:
```python
allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
```

### C2 — No authentication on any endpoint
**Files:** All routes in `routes/routes.py`  
**Risk:** Any anonymous caller can upload documents, query, clear the entire index (`DELETE /documents`), or clear the knowledge graph (`DELETE /kg`) — no token, no API key, nothing.  
**Fix:** Add OAuth2 bearer token or API-key header dependency on all write/delete endpoints.

### C3 — `DELETE /documents` and `DELETE /kg` unprotected
**File:** `routes/routes.py`  
**Risk:** A single HTTP call wipes all indexed documents or the entire knowledge graph with no confirmation and no audit trail.  
**Fix:** Require admin-level auth; add soft-delete / confirmation mechanism in production.

---

## HIGH

### H1 — API keys printed to logs
**File:** `main.py`  
**Code:** `logger.warning("⚠️  HUGGINGFACE_API_KEY not set!")` — while not printing the value, subsequent debug tracebacks could expose env values.  
**Risk:** Log aggregators / stdout capture can leak key presence info; tracebacks in debug mode expose `os.environ`.  
**Fix:** Use `LOG_LEVEL=INFO` in production (never DEBUG); never log env values.

### H2 — Bare `except:` blocks hide all errors
**Files:** `main.py` (multiple), `routes/routes.py` (Firebase update helper)  
**Risk:** Silent failures — security exceptions, import errors, and runtime crashes all swallowed without trace. Attacker probing for error patterns gets no useful feedback (good) but legitimate failures also go undetected (bad).  
**Fix:** Replace all bare `except:` with `except Exception as e: logger.error(...)` — already done in `_fb_update` lambda but not consistently elsewhere.

### H3 — No file size or type validation on upload
**File:** `routes/routes.py` — `/upload` endpoint  
**Risk:** Attacker can upload a 500 MB file, filling disk. No MIME-type check means any file extension accepted.  
**Fix:**
```python
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB
content = await file.read()
if len(content) > MAX_UPLOAD_BYTES:
    raise HTTPException(413, "File too large")
ALLOWED_EXT = {".pdf", ".txt", ".docx", ".jpg", ".jpeg", ".png"}
if ext not in ALLOWED_EXT:
    raise HTTPException(415, f"Unsupported file type: {ext}")
```

### H4 — No request rate limiting
**Files:** All endpoints  
**Risk:** Unconstrained POST /query / POST /upload can saturate the LLM and embedding model, causing denial of service.  
**Fix:** Add `slowapi` rate limiter:
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
@app.post("/query")
@limiter.limit("30/minute")
```

### H5 — Temporary files not always cleaned up on error
**File:** `routes/routes.py` — `/upload` handler  
**Risk:** If OCR or processing raises before the `finally: os.unlink(temp_path)` block, the temp file persists in the OS temp directory, potentially containing sensitive document data.  
**Fix:** The `try/finally` block is present but only in the inner try — verify it runs on every error path. Also set `delete=True` where possible or use `contextlib.ExitStack`.

### H6 — `FIREBASE_CREDENTIALS_PATH` points to a file on disk
**File:** `storage/firebase_client.py`  
**Risk:** Service-account JSON with private key stored on disk — if path is relative (`./firebase-credentials.json`) and the working directory is the project root, any process with read access gets full Firebase access.  
**Fix:** Use `GOOGLE_APPLICATION_CREDENTIALS` env var or load credential JSON from an environment variable (base64-encoded secret) rather than a file path.

---

## MEDIUM

### M1 — No input length limit on `/query`
**File:** `routes/routes.py`  
**Risk:** A 100 000-token query string will be embedded and sent to the LLM — high cost, potential DoS.  
**Fix:**
```python
class QueryInput(BaseModel):
    query: str = Field(..., max_length=4000)
```

### M2 — No request ID / correlation ID
**Files:** All routes  
**Risk:** Cannot correlate a client error report with server logs. Makes security incident investigation very slow.  
**Fix:** `core/middleware.py` — RequestIDMiddleware injects `X-Request-ID` header and adds it to log context.

### M3 — Exception details exposed in HTTP responses
**File:** `routes/routes.py`  
**Code:** `raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")`  
**Risk:** Full Python exception messages (including file paths, variable names, stack traces for some exceptions) returned to the client. An attacker learns internal paths and variable names.  
**Fix:** Log the full exception server-side; return a generic error message to the client:
```python
logger.error(f"...", exc_info=True)
raise HTTPException(500, "Internal server error — see server logs")
```

### M4 — No HTTPS enforcement
**Files:** `main.py`, `start_server.bat`  
**Risk:** All traffic including document content and API keys sent in plaintext on the network.  
**Fix:** Put a reverse proxy (nginx, Caddy, or Railway's built-in TLS) in front of uvicorn for production.

### M5 — `allow_credentials=True` with wildcard origin
**File:** `main.py`  
**Risk:** Browsers block `credentials=true` + `origin=*` as a security feature — this combination is technically invalid and may cause confusing CORS errors.  
**Fix:** Set `allow_credentials=False` when using wildcard, or specify exact origins.

### M6 — Knowledge Graph stored in plain JSON on disk
**File:** `knowledge_graph/kg_manager.py` — `kg_store.json`  
**Risk:** Extracted PII (names, addresses, IDs, DOBs from documents) written to an unencrypted JSON file on disk.  
**Fix:** Encrypt at rest or store in a proper database with access controls.

---

## LOW

### L1 — Logging level defaults to INFO — may expose PII
**File:** `config.py`, `main.py`  
**Risk:** Field extractor and RAG engine log extracted text samples (`logger.info(f"Extracted {field_name}: {value}")`). In production, these logs will contain PII (names, IDs, dates).  
**Fix:** Log field names but not values in production; use `LOG_LEVEL=WARNING` for production deployments.

### L2 — No audit log for document uploads
**File:** `routes/routes.py`  
**Risk:** No record of which IP uploaded which document at what time (outside of Firebase, which is optional).  
**Fix:** Structured audit log on every upload / delete action.

### L3 — `pyyaml` and `networkx` not version-pinned
**File:** `requirements.txt`  
**Risk:** Supply-chain attack via malicious version published to PyPI between installs.  
**Fix:** Pin all dependencies to exact versions in production; use `pip-compile` or Poetry lockfile.

### L4 — `.env.bak` / `.env.example` checked into VCS root
**Files:** `.env.bak` (in original back-end)  
**Risk:** Backup env files may contain real credentials if developer accidentally backed up an active `.env`.  
**Fix:** Ensure `.gitignore` covers `*.bak`, `.env`, `.env.*` (except `.env.example`).

---

## Remediation Priority

| Priority | Action | Effort |
|----------|--------|--------|
| P0 | Add auth (API key at minimum) to write/delete endpoints | Medium |
| P0 | Restrict CORS to known origins | Low |
| P1 | File size + type validation on /upload | Low |
| P1 | Generic error messages to client, full stack to logs | Low |
| P1 | Request ID middleware | Low |
| P2 | Rate limiting (slowapi) | Low |
| P2 | Input length limits on /query | Low |
| P2 | Encrypt KG store at rest | Medium |
| P3 | HTTPS via reverse proxy | Medium |
| P3 | Audit logging | Medium |
| P3 | Pin all dependency versions | Low |
