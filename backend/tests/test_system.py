"""Unit tests for system/health/observability endpoints."""


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["name"]
    assert "docs" in body


def test_health_always_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] in ("healthy", "degraded")


def test_version(client):
    r = client.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert "python" in body
    assert "uptime_seconds" in body


def test_readiness_returns_200_or_503(client):
    r = client.get("/readiness")
    assert r.status_code in (200, 503)


def test_status_detail(client):
    r = client.get("/status")
    assert r.status_code == 200
    body = r.json()
    assert "components" in body
    assert "diagnostics" in body


def test_diagnostics_report(client):
    r = client.get("/diagnostics")
    assert r.status_code == 200
    assert "checks" in r.json()


def test_openapi_schema_is_valid(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"]
    assert len(schema["paths"]) > 50, "expected all domain routers to be registered"
    # Every path/method combination must have at least one tag (Swagger cleanliness)
    untagged = [
        f"{method.upper()} {path}"
        for path, methods in schema["paths"].items()
        for method, op in methods.items()
        if method in ("get", "post", "put", "delete", "patch") and not op.get("tags")
    ]
    assert not untagged, f"Untagged operations found (Swagger 'default' bucket): {untagged}"


def test_swagger_ui_loads(client):
    r = client.get("/docs")
    assert r.status_code == 200
    assert b"swagger" in r.content.lower()


def test_redoc_loads(client):
    r = client.get("/redoc")
    assert r.status_code == 200


def test_metrics_endpoint_exposed(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    # Prometheus text-exposition format
    assert b"# HELP" in r.content or b"# TYPE" in r.content


def test_metrics_not_in_openapi_schema(client):
    """The /metrics endpoint should be hidden from the public API docs."""
    r = client.get("/openapi.json")
    assert "/metrics" not in r.json()["paths"]


def test_security_headers_present(client):
    r = client.get("/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"


def test_request_id_header_present(client):
    r = client.get("/health")
    assert "X-Request-ID" in r.headers
