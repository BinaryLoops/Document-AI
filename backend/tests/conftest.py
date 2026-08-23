"""
Shared pytest fixtures for the DocuMind AI backend test-suite.

The whole app (including all lazily-registered domain routers) is started
once per test session via FastAPI's TestClient context manager, which
triggers the real `lifespan()` startup/shutdown in main.py. Heavy ML
dependencies (torch, faiss, spaCy, sentence-transformers) are optional —
the app is designed to start in "degraded mode" without them, and most
tests below only rely on the lightweight code paths.
"""
from __future__ import annotations

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Generous rate limits during tests -- the security rate limiter is exercised
# explicitly in test_security.py instead.
os.environ.setdefault("RATE_LIMIT_RPM", "6000")
os.environ.setdefault("RATE_LIMIT_BURST", "500")
os.environ.setdefault("APP_ENV", "testing")


@pytest.fixture(scope="session")
def app():
    from main import app as fastapi_app
    return fastapi_app


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def admin_token(client):
    r = client.post(
        "/auth/login",
        json={"role": "system_admin", "employee_id": "ADMIN-001", "password": "Admin@9999"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture()
def issuing_authority_token(client):
    r = client.post(
        "/auth/login",
        json={
            "role": "issuing_authority",
            "department_code": "COLLECTOR-PUNE",
            "employee_id": "ISS-PUNE-001",
            "password": "IssAuth@5678",
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]
