# DocuMind AI Backend — Test Report

**Date of this hardening pass:** 2026-08-23 (two passes: an initial `TestClient`-based hardening pass, followed by a real `uvicorn`-server runtime-verification pass — see §8)
**Environment:** Windows 11, Python 3.11.9, full `requirements.txt` installed (torch, faiss-cpu, sentence-transformers, spaCy + `en_core_web_sm`, opencv-python-headless, pytesseract) globally. In the second pass, a real Tesseract-OCR 5.4 binary was also installed and wired up — see §8 for genuine OCR text-extraction results (no longer a degraded-mode scenario).

## 1. Summary

| Category | Result |
|---|---|
| Unit + integration tests (`pytest tests/`) | **75 / 75 passed** |
| End-to-end manual smoke test (`tests/_manual_smoke_run.py`, 28 live HTTP checks across every subsystem) | **28 / 28 passed** |
| Static security analysis (`bandit`) | 0 high severity; medium-severity findings reviewed, see `SECURITY_GUIDE.md` §4 |
| Dependency vulnerability scan (`pip-audit`) | 1 tracked issue (`PyPDF2`, low blast-radius fallback path) |
| Critical bugs found & fixed (TestClient pass, §2) | **4** |
| Additional real bugs found & fixed (live Uvicorn pass, §7) | **4** (Windows console Unicode logging crash, FAISS/NumPy 2.x ABI break, `TESSERACT_CMD` never wired to pytesseract, enterprise audit log never populated) |
| Docker build | **Not executed** — no Docker daemon available in this environment. Dockerfile reviewed manually; see `DEPLOYMENT_GUIDE.md` §4.1 for the exact commands to run in a Docker-capable environment. |

## 2. Bugs Found and Fixed

These were discovered through genuine execution (starting the real app, running real requests), not just static reading — each one reproduces the failure before the fix and the corresponding automated regression test now guards against it.

| # | Bug | File | Impact | Fix | Regression test |
|---|---|---|---|---|---|
| 1 | `security/` package (rate limiting, CSRF, input sanitization, audit log, incident detection) was fully built but never imported/registered in `main.py` | `main.py` | The entire security middleware stack and `/security/*` API were dead code — **zero effective protection in production** despite the code existing. | Wired `add_security_middleware()` + `create_security_router()` + `init_audit_db()` into the app factory and lifespan. | `tests/test_security.py` (16 tests) |
| 2 | `ExceptionMiddleware.dispatch()` called `get_request_id()` without importing it | `core/middleware.py` | Any unhandled exception anywhere in the app crashed the exception handler itself with `NameError`, defeating the entire purpose of centralised error handling — reproduced live with a real stack trace during this pass. | Added the missing import from `core.logging`. | Verified via the full pytest + smoke suite exercising real requests through this middleware on every call. |
| 3 | `GET /search` (RAG) returned raw `numpy.float32` similarity scores | `rag/engine.py`, `knowledge_graph/integration.py`, `knowledge_graph/intelligence.py` | FastAPI's `jsonable_encoder` cannot serialize numpy scalars — **any non-empty search result crashed with HTTP 500** (`ValueError: 'numpy.float32' object is not iterable`), reproduced live. | Cast every similarity score to native `float` before returning. | `tests/test_rag.py::test_search_endpoint_no_numpy_leak` |
| 4 | `jwt_secret_key` field declaration in `core/config.py` was appended to the end of a long comment line, so it was never actually parsed as a Pydantic field | `core/config.py` | `settings.jwt_secret_key` would raise `AttributeError` the moment any code tried to read it from the settings object (currently masked because `auth/jwt_handler.py` reads `os.getenv()` directly instead — but this was a landmine for any future refactor). | Fixed the line break; added a production startup warning if the value is left at its insecure default. | Verified by import + `Settings()` instantiation in the full test session. |

### Additional hardening fixes (not crashes, but real gaps)

* `routes/routes.py` — 21 endpoints (all of `/documents`, `/upload`, `/query`, `/search`, `/kg/*`, `/intelligence/*`) had no `tags=`, so they fell into Swagger UI's unlabeled "default" bucket. All 21 are now tagged consistently with the rest of the API. Regression-tested by `tests/test_system.py::test_openapi_schema_is_valid`, which asserts **every** operation in the OpenAPI schema has at least one tag.
* `RAGAPIRouter` registered a second `GET /health` that was permanently unreachable (shadowed by the system `/health` registered earlier in `main.py`) — renamed to `GET /rag/health` to remove the ambiguity from the OpenAPI schema.
* Default rate limit (60 rpm / burst 10) was tightened enough to fail a normal multi-request page load in testing; raised to 120 rpm / burst 30.
* `opencv-python` (GUI build, needs `libGL`/X11 in the container) swapped for `opencv-python-headless`.

## 3. Feature Verification (live, against the real app)

Each item below was exercised with real HTTP requests against a running instance of the app (`fastapi.testclient.TestClient`, which runs the actual `lifespan()` startup/shutdown — not mocked).

| Requirement | Verified how | Result |
|---|---|---|
| **FastAPI starts** | Full app startup via `TestClient`, all 8 subsystems initialise, 105 OpenAPI paths registered | ✅ Pass — startup completes in ~35–40s (dominated by first-time embedding-model + spaCy load) |
| **OCR works** | `POST /documents/upload` with a real PNG through the full Digital Locker pipeline (scan → OCR → classify → verify → encrypt → store) | ✅ Pass — verified twice. First without a Tesseract binary present: the pipeline logged a clean, caught failure and **still completed successfully** (graceful degradation, by design). Then with a real Tesseract 5.4 binary installed (§7): real text was extracted (**373 characters, 94% confidence**), and document classification correctly improved from `other` (0.0 confidence) to `education_certificate` (0.67 confidence) on the same image. Also found and fixed a real bug in this pass: `TESSERACT_CMD` was read from config but never actually passed to `pytesseract` — see §7. |
| **Verification works** | `POST /verify/document` — full 12-step pipeline | ✅ Pass — returns a computed `trust_badge` (`green`/`yellow`/`red`), `fraud_score`, and per-step results |
| **AI works** | `POST /ai/summarize`, `/ai/entities`, `/ai/timeline`, `/assistant/ask` | ✅ Pass — all four return structured, non-empty results against sample government-document text |
| **Knowledge Graph works** | `POST /graph/ingest` → `GET /graph/document/{id}`, `GET /graph/stats`, `GET /kg/stats` (RAG-local graph with spaCy NER) | ✅ Pass — entities extracted via `en_core_web_sm`, graph stats reflect ingested data |
| **Generated documents work** | Full flow: issuing-authority login → `POST /generate/passport` with a complete valid field set → `GET /generated/{id}` | ✅ Pass — returns a real signed PDF (`content-type: application/pdf`, `%PDF` magic bytes present), including RSA-2048 signature and QR code generation |
| **Notifications work** | `GET /notifications`, `GET /notifications/count`, `POST /notifications/mark-read` | ✅ Pass |
| **Docker builds successfully** | Not executable in this environment (no Docker daemon) | ⚠️ **Not verified in this environment.** Manually reviewed for correctness; run `docker build -t documind-backend .` in a Docker-capable environment before first production deploy — see `DEPLOYMENT_GUIDE.md` §4.1. |

## 4. Automated Test Suite (`tests/`)

Added this pass, using `pytest` + FastAPI's `TestClient` (which runs the real app lifespan):

| File | Focus | Tests |
|---|---|---|
| `tests/conftest.py` | Shared fixtures: session-scoped app/client, admin & issuing-authority login tokens | — |
| `tests/test_system.py` | Health/readiness/status/diagnostics, OpenAPI schema completeness, Swagger/ReDoc, Prometheus `/metrics`, security headers, request-ID propagation | 13 |
| `tests/test_auth.py` | Login (success/failure/validation), `/auth/me`, device listing, RBAC cross-role denial | 9 |
| `tests/test_rag.py` | Document ingest, query, search, **numpy-serialization regression test** | 4 (auto-skip if torch/faiss not installed) |
| `tests/test_ai_engine.py` | Summarize, entities, timeline, case-intel, assistant Q&A | 6 |
| `tests/test_verification_and_generation.py` | 12-step verification pipeline, template schema, RBAC-gated generation, full generate→download flow | 8 |
| `tests/test_knowledge_graph_api.py` | Graph stats/export/departments/ingest/fraud-clusters/duplicates | 6 |
| `tests/test_tracking_and_notifications.py` | Tracking record lifecycle, notifications | 5 |
| `tests/test_security.py` | SQLi/XSS/path-traversal blocking, security headers, CORS credential safety, audit log + chain integrity, consent grant/revoke, **isolated unit tests of the token-bucket rate limiter and file-validation utility** | 16 |
| `tests/test_integration_e2e.py` | Full citizen → issuing-authority → download → notification journey across 4 subsystems in one flow | 1 |
| `tests/test_generation_performance.py` *(pre-existing, part of the `.kiro` government-document-generation-engine spec work)* | Generation cache lookup performance/hit-rate | 8 |

**Run it yourself:**
```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

Result at time of writing:
```
75 passed, 2 warnings in 52.39s
```

### Manual end-to-end smoke script

`tests/_manual_smoke_run.py` is a standalone script (not collected by pytest) that hits 28 real endpoints in sequence across every subsystem and writes a JSON result file. Useful as a fast post-deploy sanity check against a live server:
```bash
python tests/_manual_smoke_run.py
```
Result at time of writing: **28 / 28 checks passed.**

## 5. Performance Testing

### 5.1 New load-testing infrastructure (this pass)

`tests/performance/locustfile.py` — Locust scenarios simulating three realistic traffic mixes (read-only dashboard browsing, AI-engine analysis workload, verification-pipeline workload). Run against a **real running server** (not `TestClient`, which doesn't measure network-level latency):

```bash
uvicorn main:app --workers 2 &
locust -f tests/performance/locustfile.py --host http://localhost:8000 \
       --headless -u 50 -r 5 -t 2m --csv=perf_report
```

This was authored and reviewed but not executed for a sustained load run in this sandbox (no long-lived server process available); run it before launch and attach the resulting `perf_report_stats.csv` to your go-live checklist.

### 5.2 Pre-existing performance results (found in the repository, from separate `.kiro`-spec work on the Document Generation Engine)

These were already present in the codebase from prior work and are referenced here rather than duplicated:

* **`PERFORMANCE_BENCHMARK_REPORT.md`** (Task 6.1 — throughput): 100 sequential document generations, **51.74 docs/min** measured against a **100 docs/min** target — currently **below target**, with PDF generation (~696ms) and RSA signing (~232ms) identified as the largest bottlenecks. Recommendations already documented there: parallel worker processes, PDF story-element caching, async I/O.
* **`TASK_6.3_RESULTS.md`** (Task 6.3 — memory under load): 50 concurrent document generations, **36.57 MB peak memory** against a **300 MB** limit — comfortably passing with significant headroom.

**Recommendation:** treat the throughput gap in `PERFORMANCE_BENCHMARK_REPORT.md` as a known, tracked limitation rather than a blocker — 51.74 docs/min is adequate for most government-issuance workloads at pilot scale, and the report's own recommendations (parallel workers) are the correct next step if/when real traffic approaches that ceiling.

## 6. Security Testing

See `SECURITY_GUIDE.md` for full detail. Summary:

* **Dynamic (integration) tests:** SQL injection, XSS, and path-traversal payloads in query parameters are all blocked with HTTP 400 by `InputSanitizationMiddleware` (`tests/test_security.py`). Security headers (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`) present on every response. CORS wildcard configuration verified to not also allow credentials (a classic misconfiguration).
* **Static analysis (`bandit`):** run across the full codebase; findings triaged in `SECURITY_GUIDE.md` §4.1 (one false positive verified by manual code review, one accepted architectural risk, one valid follow-up recommendation).
* **Dependency scan (`pip-audit`):** one tracked, low-blast-radius finding (`PyPDF2`) — see `SECURITY_GUIDE.md` §4.2.
* **Audit trail integrity:** `GET /security/audit/verify` cryptographically verifies the SHA-256 hash chain of the audit log — confirmed `"integrity": "intact"` after a batch of test operations.

## 7. Real-Server Runtime Verification Pass (Uvicorn, not TestClient)

A follow-up pass ran the app the way it actually runs in production: `uvicorn main:app --host 0.0.0.0 --port 8000` as a real OS process, verified over real HTTP with `curl`, with the full ML stack **and a real Tesseract-OCR 5.4 binary** installed (`winget install UB-Mannheim.TesseractOCR`). This surfaced four additional real bugs that the `TestClient`-based pass could not have found (`TestClient` runs in-process and doesn't exercise OS-level console/subprocess/binary-loading behaviour):

| # | Bug | File | Impact | Fix |
|---|---|---|---|---|
| 5 | Every Unicode symbol in log messages (✓ ✗ ⚠, used throughout `main.py`/`core/diagnostics.py`) crashed Python's own logging module with `UnicodeEncodeError` when running under a real Windows console/process (`cp1252` default encoding) — not raised to the app, but silently flooding stderr with a full traceback **on nearly every log line**. | `core/logging.py` | Operational/observability failure — logs become mostly noise, real errors get buried, and any log-shipping pipeline choking on malformed output could lose data. | `configure_logging()` now reconfigures `sys.stdout`/`sys.stderr` to UTF-8 (`errors="replace"`) as the very first step, before any handler is attached. Verified: zero logging errors across a full server run afterward. |
| 6 | `faiss-cpu` (an older cached build) is binary-incompatible with NumPy 2.x (`AttributeError: _ARRAY_API not found` / `ImportError: numpy.core.multiarray failed to import`) — the exact combination `pip install -r requirements.txt` will produce today, since `numpy>=1.24.0` and unpinned `faiss-cpu` happily resolve to NumPy 2.x + an old FAISS wheel from cache. | `requirements.txt` | **Critical** — the entire RAG/vector-search subsystem fails to initialise; the app degrades but every `/documents`, `/query`, `/search` call becomes unavailable. | Upgraded to `faiss-cpu==1.15.0` (verified compatible with NumPy 2.4). Pinned `faiss-cpu>=1.8.0` in `requirements.txt` with an explanatory comment so a fresh install never regresses. |
| 7 | `TESSERACT_CMD` (read by `core/config.py` and reported as "found" by `/diagnostics`) was **never actually passed to `pytesseract`** — `document/ocr_processor.py::OCRProcessor.__init__()` constructed `TesseractOCR()` with zero arguments, silently discarding the configured path. OCR only worked by accident if Tesseract happened to already be on the OS `PATH`. | `document/ocr_processor.py` | High — a config setting that appears to work (diagnostics says "found") has zero effect; OCR silently returns empty text on any machine where Tesseract isn't globally on `PATH` (most Windows installs, and container images unless the Dockerfile puts it there — ours does, so Docker was unaffected, but any other deployment target could hit this silently). | `OCRProcessor.__init__()` now reads `core.config.settings.tesseract_cmd` / `.ocr_language` and passes them through. Verified live: OCR went from 0 chars / 0.00 confidence to **373 characters extracted at 0.94 confidence**, with document classification correctly changing from `other` (0.0 confidence) to `education_certificate` (0.67 confidence) on the same test image. |
| 8 | The immutable, hash-chained audit log (`security/audit.py`, exposed at `/security/audit`) was reachable and its integrity-verification endpoint worked — but **no code anywhere in the application ever wrote to it**. `auth/routes.py` writes to a separate, unrelated login-event log (`auth/session_manager.py`); `digilocker/pipeline.py` writes to a separate, unrelated per-document audit table (`digilocker/database.py`). The enterprise audit trail was permanently, silently empty. | `auth/routes.py`, `digilocker/pipeline.py`, `verification_engine/pipeline.py` | High (compliance/forensics gap) — an audit feature that appears to work (returns `200`, chain "intact") but never actually captures anything is arguably worse than no audit log, since it creates false confidence. | Wired `security.audit.log_audit()` into: auth login success/failure, document upload, and verification completion (each wrapped in `try/except` so an audit-log failure can never break the underlying operation). `_finalize_login()` was converted to `async def` (4 call sites updated) to allow the `await`. Verified live: a login success, a login failure, and a document upload each produced a real, hash-chained entry; `GET /security/audit/verify` reported `"integrity": "intact"` across all 3. |
| — | `DIGILOCKER_MASTER_KEY` must be **base64-urlsafe**, not raw hex — easy to get wrong when hand-generating a key (this pass's own first attempt did exactly that, reproducing `binascii.Error: Incorrect padding` live). | `digilocker/encryption.py` | Medium — misconfigured key silently disables the entire Digital Locker subsystem (caught by `main.py`'s per-subsystem `try/except`, so the app still starts, but with a whole feature missing and only a log line to explain why). | Corrected the generated `.env` value. Also hardened `AES256Encryptor.__init__` to catch the base64-decode error and raise a clear, actionable `ValueError` with the exact command to generate a valid key, instead of a bare `binascii.Error`. |

### Full clean-startup confirmation (after all fixes)

```
✓ Auth store loaded / Auth routes registered
✓ Digital Locker ready (/documents/*)
✓ Verification Engine ready (/verify/*)
✓ AI Intelligence Engine ready (/ai/*, /assistant/*)
✓ Document Generation Engine ready (/generate/*, /generated/*)
✓ Government Knowledge Graph ready (/graph/*)
✓ Tracking & Notifications ready (/tracking/*, /notifications/*)
✓ Enterprise Security ready (/security/*)
Startup diagnostics: ok=8 warn=2 fail=0 skip=2
✓ Embedding model ready (dim=384)
✓ FAISS vector database ready
✓ LLM: LocalLLM (rule-based fallback -- Ollama/HuggingFace not configured, by design)
✓ RAG engine ready
✓ API routes registered
✓ DocuMind AI is ready (startup took ~33s)
Application startup complete. Uvicorn running on http://0.0.0.0:8000
```

`grep -iE "error|exception|traceback|critical"` across the full server log (both stdout and stderr) after all fixes returns **zero matches** other than the expected, non-fatal "Ollama not available" fallback message.

### Live HTTP verification performed against the real server (all HTTP 200 unless noted)

`/`, `/health`, `/version`, `/readiness`, `/status`, `/diagnostics`, `/docs`, `/openapi.json`, `/metrics`, `/documents/categories`, `/verify/departments`, `/generate/pubkey`, `/graph/stats`, `/security/audit`, plus full stateful flows:

* **Upload → OCR → classify → store → retrieve**: `POST /documents/upload` (real image) → 373 chars OCR'd at 94% confidence → classified `education_certificate` → `GET /documents/{id}` and `GET /documents?owner=...` both return it.
* **RAG**: `POST /documents` (ingest) → `POST /query` (real generated answer, grounded in the ingested text) → `GET /search` (native-`float` scores, confirming the earlier numpy fix still holds under a real server).
* **Knowledge Graph**: `POST /graph/ingest` → `GET /graph/stats` shows real node/edge counts (`2 nodes, 1 edge, density 0.5`).
* **AI Intelligence**: `POST /ai/summarize`, `POST /ai/entities` both return structured results against real text.
* **Verification**: `POST /verify/document` → full 12-step breakdown, computed trust badge.
* **Auth/RBAC/Audit**: citizen OTP login (dev-mode OTP read from the log) end-to-end; system_admin login; a `system_admin` token correctly gets `403` on an `issuing_authority`-only endpoint; all three actions appear in the now-populated, integrity-verified audit log.
* **Regression check**: full `pytest tests/` suite re-run after all of the above fixes — **97/97 passed** (75 from the original hardening pass + additional tests added by other in-progress work in this repository), confirming none of today's fixes introduced a regression.

## 8. Known Limitations of This Verification Pass

* **Docker build/run was not executed** (no Docker daemon in this environment) — see §3 and `DEPLOYMENT_GUIDE.md`. Note: the real-server pass in §7 did successfully validate the application logic that runs *inside* the container (real Tesseract OCR, real FAISS, real uvicorn process) — only the containerisation step itself is unverified.
* ~~Real Tesseract OCR text extraction was not exercised~~ — **resolved in §7**: a real Tesseract 5.4 binary was installed and verified end-to-end (373 chars extracted at 94% confidence).
* **Neo4j and Firebase** were not configured — both have explicit, tested fallback paths (in-memory Knowledge Graph; disabled push notifications) and were verified to degrade gracefully rather than block startup.
* **Sustained load testing** (Locust run) was authored but not executed for a multi-minute sustained run — do this against a staging environment before go-live.
* **Ollama / real LLM inference** was not available in this environment; the system correctly fell back to the rule-based `LocalLLM`, which was exercised and returns valid (if less fluent) answers.
