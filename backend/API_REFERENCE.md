# DocuMind AI Backend — API Reference

**Version:** 1.0.0 · **Base URL (local):** `http://localhost:8000` · **Interactive docs:** `/docs` (Swagger UI) and `/redoc` (ReDoc)

This document is a human-readable index of every endpoint exposed by the backend. For exact request/response schemas, always prefer the live OpenAPI schema at `GET /openapi.json` or the Swagger UI at `/docs` — both are generated directly from the code and are guaranteed to stay in sync.

> As part of production hardening, every endpoint in this API is now tagged
> (previously ~21 endpoints in the RAG router had no `tags=` and fell into
> an unlabeled "default" bucket in Swagger UI — see `TEST_REPORT.md`). The
> table of contents below matches the Swagger UI grouping exactly.

## Table of Contents

1. [System & Observability](#1-system--observability)
2. [Authentication (`/auth`)](#2-authentication-auth)
3. [Digital Locker (`/documents`)](#3-digital-locker-documents)
4. [Verification Engine (`/verify`)](#4-verification-engine-verify)
5. [AI Intelligence (`/ai`, `/assistant`)](#5-ai-intelligence-ai-assistant)
6. [Document Generation (`/generate`, `/generated`)](#6-document-generation-generate-generated)
7. [Knowledge Graph (`/graph`)](#7-knowledge-graph-graph)
8. [Tracking & Notifications (`/tracking`, `/notifications`)](#8-tracking--notifications)
9. [Security (`/security`)](#9-security-security)
10. [Core RAG Engine (`/documents`, `/query`, `/search`, `/kg`, `/intelligence`)](#10-core-rag-engine)
11. [Authentication & Authorization Model](#11-authentication--authorization-model)
12. [Common Error Format](#12-common-error-format)

---

## 1. System & Observability

These endpoints are always available, even if every domain subsystem below fails to initialise (the app is designed to degrade gracefully rather than crash).

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | none | API root — name, version, status, links |
| GET | `/version` | none | Version, build date, Python/platform info, uptime |
| GET | `/health` | none | Liveness probe — **always returns 200** (use for container `HEALTHCHECK` / k8s `livenessProbe`) |
| GET | `/readiness` | none | Readiness probe — 200 only once the RAG engine + embedder are fully up, else 503 (use for k8s `readinessProbe`) |
| GET | `/status` | none | Per-component status (RAG, vector DB, LLM, KG, Firebase) |
| GET | `/diagnostics` | none | Full startup diagnostics report (dependency checks, versions, warnings) |
| GET | `/metrics` | none | Prometheus text-exposition metrics (hidden from `/docs`; see `DEPLOYMENT_GUIDE.md`) |
| GET | `/docs` | none | Swagger UI |
| GET | `/redoc` | none | ReDoc UI |
| GET | `/openapi.json` | none | Raw OpenAPI 3.x schema |

---

## 2. Authentication (`/auth`)

Supports four roles with different login flows: `citizen` (Aadhaar + phone OTP), `government_official`, `system_admin`, `issuing_authority` (all three: employee/department credentials + optional TOTP MFA).

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/login` | none | Step 1 — primary credential check (role-specific fields) |
| POST | `/auth/otp` | none | Step 2 (Citizen) — verify phone OTP, completes login |
| POST | `/auth/mfa` | none | Step 2 (Official/Admin/IssuingAuthority) — verify TOTP or backup code |
| POST | `/auth/logout` | Bearer | Revoke current access token + session |
| POST | `/auth/refresh` | none (refresh token in body) | Rotate access + refresh tokens |
| GET | `/auth/me` | Bearer | Current user profile + effective permissions |
| GET | `/auth/devices` | Bearer | Devices registered to the current user |
| POST | `/auth/revoke-session` | Bearer | Revoke a specific session, or all sessions |
| GET | `/auth/history` | Bearer | Recent login events for the current user |
| POST | `/auth/mfa/setup` | Bearer (Official/Admin/IssuingAuthority) | Generate TOTP secret + QR + backup codes |
| POST | `/auth/mfa/verify` | Bearer | Confirm TOTP code to activate MFA |
| POST | `/auth/admin/revoke-user` | Bearer (SystemAdmin) | Revoke **all** sessions for a target user |

**Demo credentials** (development/testing only — see `SECURITY_GUIDE.md` for why these must be rotated before production):

| Role | Login fields | Password / OTP |
|---|---|---|
| citizen | `role=citizen`, `aadhaar_number=123456789012`, `phone=+919876543210` | OTP printed to server log in dev mode |
| government_official | `role=government_official`, `employee_id=GOV-MH-10042` | `Official@1234` |
| system_admin | `role=system_admin`, `employee_id=ADMIN-001` | `Admin@9999` |
| issuing_authority | `role=issuing_authority`, `department_code=COLLECTOR-PUNE`, `employee_id=ISS-PUNE-001` | `IssAuth@5678` |

---

## 3. Digital Locker (`/documents`)

Encrypted document storage with a full ingestion pipeline: upload → malware scan → OCR → AI classification → verification → AES-256-GCM encryption → storage.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/documents/upload` | owner (form field) | Upload a document (PDF/JPG/PNG/DOCX, max 20MB) through the full pipeline |
| GET | `/documents` | owner filter | List documents with filters + pagination |
| GET | `/documents/categories` | none | List supported document categories + field schemas |
| GET | `/documents/search` | none | Free-text document search |
| GET | `/documents/{document_id}` | owner/authority | Get full document metadata |
| GET | `/documents/{document_id}/download` | owner/authority | Download the decrypted original file |
| GET | `/documents/{document_id}/preview` | owner/authority | PNG preview image |
| GET | `/documents/{document_id}/thumbnail` | owner/authority | PNG thumbnail |
| GET | `/documents/{document_id}/versions` | owner/authority | Immutable version history |
| POST | `/documents/archive` | owner | Archive a document |
| POST | `/documents/request-delete` | owner | Request document deletion (goes to admin approval queue) |
| GET | `/documents/deletion-requests` | admin | List pending deletion requests |
| POST | `/documents/deletion-requests/{request_id}/approve` | admin | Approve a deletion request |
| POST | `/documents/deletion-requests/{request_id}/reject` | admin | Reject a deletion request |

---

## 4. Verification Engine (`/verify`)

Runs a 12-step government document verification pipeline: upload validation → OCR quality → AI classification → serial/QR/template/issuer verification → registry check → duplicate/fraud scoring → trust badge assignment (`green` / `yellow` / `red`).

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/verify/document` | none | Run the full 12-step verification pipeline |
| GET | `/verify/status/{verification_id}` | none | Get verification status + result |
| POST | `/verify/manual-review` | reviewer | Submit a manual review outcome for a flagged document |
| GET | `/verify/history/{document_id}` | none | Full verification history for a document |
| GET | `/verify/pending-reviews` | reviewer | List documents awaiting manual review |
| GET | `/verify/departments` | none | List department-specific verification modules |

---

## 5. AI Intelligence (`/ai`, `/assistant`)

Document understanding built on top of extracted OCR/plain text — no auth required (stateless analysis of text you provide in the request body).

| Method | Path | Description |
|---|---|---|
| POST | `/ai/summarize` | Key points, dates/deadlines, orgs, people, locations |
| POST | `/ai/entities` | Classified entities: citizens, officers, departments, courts, institutions |
| POST | `/ai/timeline` | Chronological event extraction with ISO date parsing |
| POST | `/ai/case-intel` | Cross-document analysis: related cases, duplicate identities, conflicting records (2+ documents) |
| POST | `/assistant/ask` | Evidence-backed Q&A over a single document's text |

---

## 6. Document Generation (`/generate`, `/generated`)

Issues signed government documents (RSA-2048 digital signature + QR code) as PDFs. All `POST /generate/*` endpoints require the `issuing_authority` role and `Permission.GENERATE_DOCUMENT`.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/generate/passport` | Issuing Authority | Generate a Passport |
| POST | `/generate/license` | Issuing Authority | Generate a Driving Licence |
| POST | `/generate/birth` | Issuing Authority | Generate a Birth Certificate |
| POST | `/generate/income` | Issuing Authority | Generate an Income Certificate |
| POST | `/generate/land` | Issuing Authority | Generate a Land Record |
| GET | `/generated/{document_id}` | owner or Issuing Authority | Download the generated PDF |
| GET | `/generate/status/{request_id}` | owner or Issuing Authority | Poll generation request status |
| GET | `/generate/list` | Admin / Issuing Authority | List all issued documents |
| GET | `/generate/my` | Bearer | List documents issued to the current user |
| GET | `/generate/requests` | Issuing Authority | List pending generation requests |
| POST | `/generate/approve/{request_id}` | Issuing Authority | Approve a pending request |
| POST | `/generate/reject/{request_id}` | Issuing Authority | Reject a pending request |
| POST | `/generate/revoke/{document_id}` | Issuing Authority | Revoke an issued document |
| GET | `/generate/verify/{document_number}` | **public** | QR-scan verification — no auth (this is what the printed QR code links to) |
| GET | `/generate/template/{doc_type}` | none | Field schema for a document type (labels, validation, required fields) |
| GET | `/generate/pubkey` | none | RSA public signing key (PEM) for independent signature verification |

---

## 7. Knowledge Graph (`/graph`)

Entity/relationship graph connecting citizens, documents, officers, departments, and cases. Backed by an in-memory graph by default, or Neo4j if `NEO4J_URI`/`NEO4J_PASSWORD` are configured.

| Method | Path | Description |
|---|---|---|
| GET | `/graph/document/{document_id}` | 2-hop subgraph around a document |
| GET | `/graph/citizen/{citizen_id}` | 2-hop subgraph around a citizen |
| GET | `/graph/case/{case_id}` | 2-hop subgraph around a case |
| GET | `/graph/officer/{officer_id}` | 2-hop subgraph around an officer |
| GET | `/graph/stats` | Node/edge counts, density, connected components |
| GET | `/graph/export` | Full graph in D3.js-compatible JSON |
| GET | `/graph/departments` | Department-centric view (officers, documents, cases) |
| GET | `/graph/timeline` | Chronological timeline extracted from graph metadata |
| GET | `/graph/fraud-clusters` | Suspicious tightly-connected entity clusters, risk-scored |
| GET | `/graph/duplicates` | Fuzzy-matched potential duplicate citizen identities |
| POST | `/graph/ingest` | Ingest extracted entities from a document into the graph |

---

## 8. Tracking & Notifications

| Method | Path | Description |
|---|---|---|
| GET | `/tracking/{application_id}` | Application tracking status |
| GET | `/tracking/document/{document_id}` | Tracking record by document ID |
| POST | `/tracking/create` | Create a new tracking record |
| POST | `/tracking/update/{application_id}` | Update application stage |
| GET | `/notifications` | User notifications (query param `user_id`) |
| POST | `/notifications/mark-read` | Mark notifications as read |
| GET | `/notifications/count` | Unread notification count |

---

## 9. Security (`/security`)

Newly wired into the running application as part of production hardening (see `SECURITY_GUIDE.md` and `FINAL_BACKEND_REPORT.md` — this module existed in the codebase but was never registered in `main.py` prior to this work).

| Method | Path | Description |
|---|---|---|
| GET | `/security/audit` | Query the immutable, hash-chained audit log |
| GET | `/security/audit/verify` | Verify audit log chain integrity (tamper detection) |
| GET | `/security/events` | Security incidents (brute force, device change, geo anomaly, etc.) |
| GET | `/security/anomalies` | Current anomaly scores per tracked user |
| GET | `/security/custody/{document_id}` | Full chain-of-custody for a document |
| POST | `/security/consent` | Grant user consent (data_processing / sharing / storage / analytics) |
| DELETE | `/security/consent` | Revoke a user's consent |
| GET | `/security/consent/{user_id}` | Get all consent records for a user |

---

## 10. Core RAG Engine

Registered at root level (no path prefix) by `routes/routes.py`. Powers general-purpose document Q&A independent of the government-specific engines above.

| Method | Path | Description |
|---|---|---|
| POST | `/documents` | Ingest raw text documents into the FAISS vector index |
| POST | `/upload` | Upload + process document files (PDF/DOCX/images with OCR) into the index |
| GET | `/documents/{document_id}/status` | Processing status of an ingested document |
| POST | `/query` | Ask a question — hybrid semantic + keyword retrieval + LLM answer |
| GET | `/search` | Retrieve relevant chunks without generating an LLM answer |
| DELETE | `/documents` | Clear all indexed documents |
| GET | `/rag/health` | RAG-subsystem-specific health (embedder + vector DB only) — renamed from a conflicting `/health` route; see `TEST_REPORT.md` |
| GET | `/kg/stats` / `/kg/graph` / `/kg/entity/{name}` | RAG-local knowledge graph inspection |
| POST | `/kg/build` / DELETE `/kg` | (Re)build or clear the RAG-local knowledge graph |
| GET | `/kg/visualize` | Interactive HTML graph visualisation |
| POST | `/intelligence/provenance` | Evidence chain for a query answer |
| POST | `/intelligence/cross-doc` | Shared entities/values across uploaded documents |
| POST | `/intelligence/completeness` | Field + workflow completeness checking |
| POST | `/intelligence/contradictions` | Field-level contradiction detection across documents |
| POST | `/intelligence/version` | Detect if one document supersedes another |
| POST | `/intelligence/graphrag` | Knowledge-graph-guided retrieval + generation |
| POST | `/intelligence/compare` | Structured side-by-side document comparison |
| POST | `/intelligence/explain` | Step-by-step explanation of how an answer was derived |

---

## 11. Authentication & Authorization Model

* **Token type:** JWT (HS256), issued by `POST /auth/login` (+ OTP/MFA step). Send as `Authorization: Bearer <token>`.
* **Access token TTL:** 30 minutes (default, `ACCESS_TOKEN_TTL_MINUTES`). **Refresh token TTL:** 7 days (`REFRESH_TOKEN_TTL_DAYS`). Use `POST /auth/refresh` to rotate both before expiry.
* **RBAC roles:** `citizen`, `government_official`, `system_admin`, `issuing_authority`. Permissions are enforced per-endpoint via FastAPI dependencies (`require_auth`, `require_role`, `require_permission` in `auth/rbac.py`).
* **MFA:** required for `government_official`, `system_admin`, and `issuing_authority` once enabled via `/auth/mfa/setup` + `/auth/mfa/verify` (TOTP, RFC 6238). Citizens authenticate via Aadhaar + phone OTP instead.
* **Rate limiting:** all endpoints except `/health`, `/docs`, `/openapi.json`, `/redoc` are subject to a per-IP token-bucket limiter (`RATE_LIMIT_RPM` / `RATE_LIMIT_BURST`, default 120 rpm / burst 30). See `SECURITY_GUIDE.md`.

---

## 12. Common Error Format

Unhandled exceptions and the global exception middleware return:

```json
{
  "error": "internal_server_error",
  "message": "An unexpected error occurred. Check server logs.",
  "request_id": "8a7339d0-bd70-46b6-a8b7-b5b9640e9bd7"
}
```

Validation errors (FastAPI/Pydantic, HTTP 422) return the standard FastAPI shape:

```json
{
  "detail": [
    {"type": "missing", "loc": ["body", "role"], "msg": "Field required", "input": {...}}
  ]
}
```

Every response includes an `X-Request-ID` header — include it when reporting issues so the corresponding server-side log line (and audit log entry, where applicable) can be located.
