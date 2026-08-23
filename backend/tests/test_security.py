"""
Security-focused tests.

Covers both:
  1. Integration tests against the running app (input sanitization,
     security headers, audit log, incident detection endpoints).
  2. Isolated unit tests of the rate limiter and file-validation utilities
     (imported directly, independent of the test-session-wide generous
     rate limit override in conftest.py).
"""
import asyncio

import pytest


# ── Input sanitization (integration) ─────────────────────────────────────────

@pytest.mark.parametrize("payload", [
    "1 UNION SELECT * FROM users",
    "'; DROP TABLE documents; --",
])
def test_sql_injection_in_query_param_blocked(client, payload):
    r = client.get("/search", params={"query": payload})
    assert r.status_code == 400
    assert r.json()["error"] == "malicious_input"


@pytest.mark.parametrize("payload", [
    "<script>alert(1)</script>",
    "javascript:alert(1)",
])
def test_xss_in_query_param_blocked(client, payload):
    r = client.get("/search", params={"query": payload})
    assert r.status_code == 400


def test_path_traversal_blocked(client):
    r = client.get("/documents/..%2f..%2fetc%2fpasswd")
    assert r.status_code in (400, 404)


# ── Security headers ─────────────────────────────────────────────────────────

def test_response_has_hardening_headers(client):
    r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy")
    assert r.headers.get("Permissions-Policy")


def test_cors_wildcard_disallows_credentials_by_default(client):
    """When CORS_ORIGINS='*' the app must not also allow credentials (browser
    spec forbids the combination, and it's a common misconfiguration)."""
    r = client.options(
        "/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.headers.get("access-control-allow-credentials") != "true"


# ── Audit log & incident detection (integration) ─────────────────────────────

def test_audit_log_query(client):
    r = client.get("/security/audit")
    assert r.status_code == 200
    assert "entries" in r.json()


def test_audit_chain_integrity_verification(client):
    r = client.get("/security/audit/verify")
    assert r.status_code == 200
    assert r.json()["verification"]["integrity"] in ("intact", "compromised")


def test_security_incidents_endpoint(client):
    r = client.get("/security/events")
    assert r.status_code == 200


def test_grant_and_revoke_consent(client):
    r = client.post(
        "/security/consent",
        json={"user_id": "demo-citizen-001", "consent_type": "data_processing", "purpose": "test"},
    )
    assert r.status_code == 200

    r2 = client.request(
        "DELETE",
        "/security/consent",
        json={"user_id": "demo-citizen-001", "consent_type": "data_processing"},
    )
    assert r2.status_code == 200


# ── Rate limiter (isolated unit test) ─────────────────────────────────────────

def test_rate_limiter_token_bucket_blocks_after_burst():
    from security.middleware import RateLimitMiddleware

    class DummyApp:
        async def __call__(self, *a, **kw):
            pass

    mw = RateLimitMiddleware(DummyApp(), rpm=60, burst=3)

    class DummyClient:
        host = "203.0.113.5"

    class DummyRequest:
        url = type("u", (), {"path": "/documents"})()
        headers: dict = {}
        client = DummyClient()

    async def call_next(_request):
        class R:
            headers: dict = {}
        return R()

    async def run():
        results = []
        for _ in range(5):
            resp = await mw.dispatch(DummyRequest(), call_next)
            results.append(getattr(resp, "status_code", 200))
        return results

    results = asyncio.run(run())
    # First 3 requests consume the burst; the 4th and 5th should be rejected.
    assert results.count(429) >= 2


# ── File validation utility (isolated unit test) ──────────────────────────────

def test_validate_file_accepts_valid_png():
    from security.middleware import validate_file

    png_header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20
    result = validate_file("photo.png", png_header)
    assert result["valid"] is True
    assert result["file_type"] == "png"


def test_validate_file_rejects_dangerous_extension():
    from security.middleware import validate_file

    result = validate_file("payload.exe", b"MZ" + b"\x00" * 20)
    assert result["valid"] is False
    assert any("extension" in e.lower() for e in result["errors"])


def test_validate_file_rejects_empty_file():
    from security.middleware import validate_file

    result = validate_file("empty.pdf", b"")
    assert result["valid"] is False
