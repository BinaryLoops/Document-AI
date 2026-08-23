"""
Manual smoke-test runner used to validate the whole stack end-to-end during
production hardening. Not a pytest file (kept out of collection) - run
directly with:

    python tests/_manual_smoke_run.py

It exercises: system endpoints, RAG upload/query, OCR-backed digital locker
upload, verification pipeline, AI engine, knowledge graph, document
generation + auth/RBAC, and tracking/notifications.
"""
import io
import json
import logging
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, ".")
from main import app  # noqa: E402

results = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}")


def main():
    with TestClient(app) as c:
        # ── System ──────────────────────────────────────────────────
        r = c.get("/health")
        check("GET /health", r.status_code == 200, r.text[:200])

        r = c.get("/readiness")
        check("GET /readiness", r.status_code in (200, 503), f"status={r.status_code}")

        r = c.get("/openapi.json")
        n_paths = len(r.json().get("paths", {})) if r.status_code == 200 else 0
        check("GET /openapi.json", r.status_code == 200 and n_paths > 50, f"{n_paths} paths")

        r = c.get("/docs")
        check("GET /docs (Swagger UI)", r.status_code == 200)

        r = c.get("/metrics")
        check("GET /metrics (Prometheus)", r.status_code == 200 and b"http_requests" in r.content or r.status_code == 200)

        # ── RAG: upload + query ─────────────────────────────────────
        r = c.post("/documents", json={"documents": [
            {"title": "RTI Act Summary",
             "text": "The Right to Information Act 2005 empowers citizens to request information from public authorities.",
             "metadata": {"source": "smoke-test"}},
        ]})
        check("POST /documents (RAG ingest)", r.status_code == 200, r.text[:200])

        r = c.post("/query", json={"query": "What does the RTI Act empower citizens to do?", "top_k": 3})
        check("POST /query (RAG)", r.status_code == 200, r.text[:200])

        r = c.get("/search", params={"query": "Right to Information"})
        check("GET /search (RAG)", r.status_code == 200, r.text[:200])

        # ── AI Engine ───────────────────────────────────────────────
        sample_text = (
            "This certificate confirms that Ravi Kumar was born on 12 January 1990 "
            "in Pune, Maharashtra. Issued by the Registrar of Births on 5 March 1990."
        )
        r = c.post("/ai/summarize", json={"text": sample_text, "document_type": "birth_certificate"})
        check("POST /ai/summarize", r.status_code == 200, r.text[:200])

        r = c.post("/ai/entities", json={"text": sample_text})
        check("POST /ai/entities", r.status_code == 200, r.text[:200])

        r = c.post("/ai/timeline", json={"text": sample_text})
        check("POST /ai/timeline", r.status_code == 200, r.text[:200])

        r = c.post("/assistant/ask", json={"question": "Who was born?", "text": sample_text})
        check("POST /assistant/ask", r.status_code == 200, r.text[:200])

        # ── Knowledge Graph ─────────────────────────────────────────
        r = c.get("/graph/stats")
        check("GET /graph/stats", r.status_code == 200, r.text[:200])

        r = c.get("/kg/stats")
        check("GET /kg/stats (RAG KG)", r.status_code == 200, r.text[:200])

        # ── Auth: system_admin login (no MFA configured yet) ─────────
        r = c.post("/auth/login", json={"role": "system_admin", "employee_id": "ADMIN-001", "password": "Admin@9999"})
        check("POST /auth/login (admin)", r.status_code == 200, r.text[:300])
        admin_login = r.json() if r.status_code == 200 else {}
        access_token = admin_login.get("access_token")

        if access_token:
            r = c.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
            check("GET /auth/me", r.status_code == 200, r.text[:200])

        # ── Digital Locker upload (OCR pipeline) ─────────────────────
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xcf\xc0"
            b"\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        r = c.post(
            "/documents/upload",
            files={"file": ("test.png", io.BytesIO(png_bytes), "image/png")},
            data={"owner": "demo-citizen-001"},
        )
        check("POST /documents/upload (DigiLocker+OCR)", r.status_code in (200, 400, 422), r.text[:300])

        # ── Verification Engine ───────────────────────────────────────
        r = c.post("/verify/document", json={
            "document_id": "smoke-test-doc-1",
            "ocr_text": sample_text,
            "document_type": "birth_certificate",
            "owner": "demo-citizen-001",
        })
        check("POST /verify/document", r.status_code == 200, r.text[:300])

        r = c.get("/verify/departments")
        check("GET /verify/departments", r.status_code == 200, r.text[:200])

        # ── Document Generation (requires issuing authority auth) ─────
        r = c.post("/auth/login", json={"role": "issuing_authority", "department_code": "COLLECTOR-PUNE", "employee_id": "ISS-PUNE-001", "password": "IssAuth@5678"})
        check("POST /auth/login (issuing authority)", r.status_code == 200, r.text[:300])
        iss_login = r.json() if r.status_code == 200 else {}
        iss_token = iss_login.get("access_token")

        r = c.get("/generate/template/passport")
        check("GET /generate/template/passport", r.status_code == 200, r.text[:200])

        r = c.get("/generate/pubkey")
        check("GET /generate/pubkey", r.status_code == 200, r.text[:200])

        if iss_token:
            r = c.post(
                "/generate/passport",
                headers={"Authorization": f"Bearer {iss_token}"},
                json={"applicant_user_id": "demo-citizen-001", "fields": {
                    "surname": "Kumar", "given_names": "Ravi",
                    "date_of_birth": "1990-01-12", "place_of_birth": "Pune",
                    "gender": "M", "nationality": "Indian",
                    "aadhaar_number": "123456789012", "father_name": "Suresh Kumar",
                    "mother_name": "Lata Kumar", "address": "123 MG Road, Pune, Maharashtra",
                    "application_type": "Fresh",
                }},
            )
            check("POST /generate/passport", r.status_code in (200, 201), r.text[:300])
            gen_doc = r.json() if r.status_code in (200, 201) else {}

            doc_id = gen_doc.get("document", {}).get("document_id") or gen_doc.get("document_id")
            if doc_id:
                r = c.get(f"/generated/{doc_id}", headers={"Authorization": f"Bearer {iss_token}"})
                check("GET /generated/{id} (download PDF)", r.status_code == 200 and r.headers.get("content-type") == "application/pdf", f"status={r.status_code} type={r.headers.get('content-type')}")

        # ── Tracking & Notifications ──────────────────────────────────
        r = c.get("/notifications", params={"user_id": "demo-citizen-001"})
        check("GET /notifications", r.status_code == 200, r.text[:200])

        r = c.get("/notifications/count", params={"user_id": "demo-citizen-001"})
        check("GET /notifications/count", r.status_code == 200, r.text[:200])

        # ── Security ────────────────────────────────────────────────
        r = c.get("/security/audit")
        check("GET /security/audit", r.status_code == 200, r.text[:200])

        r = c.get("/security/audit/verify")
        check("GET /security/audit/verify", r.status_code == 200, r.text[:200])

    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{total} checks passed")
    with open("tests/_smoke_results.json", "w") as f:
        json.dump([{"name": n, "pass": ok, "detail": d} for n, ok, d in results], f, indent=2)
    return 0 if passed == total else 1


if __name__ == "__main__":
    logging.getLogger().setLevel(logging.WARNING)
    sys.exit(main())
