"""Unit tests for authentication, RBAC, and session management."""


def test_admin_login_succeeds(client):
    r = client.post(
        "/auth/login",
        json={"role": "system_admin", "employee_id": "ADMIN-001", "password": "Admin@9999"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body or body.get("next") == "mfa"


def test_login_with_wrong_password_fails(client):
    r = client.post(
        "/auth/login",
        json={"role": "system_admin", "employee_id": "ADMIN-001", "password": "wrong-password"},
    )
    assert r.status_code in (401, 403)


def test_login_missing_role_returns_422(client):
    r = client.post("/auth/login", json={"employee_id": "ADMIN-001", "password": "Admin@9999"})
    assert r.status_code == 422


def test_me_requires_auth(client):
    r = client.get("/auth/me")
    assert r.status_code in (401, 403)


def test_me_with_valid_token(client, admin_token):
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert r.json()["role"] == "system_admin"


def test_me_with_invalid_token_rejected(client):
    r = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert r.status_code in (401, 403)


def test_devices_endpoint_requires_auth(client):
    r = client.get("/auth/devices")
    assert r.status_code in (401, 403)


def test_devices_endpoint_with_token(client, admin_token):
    r = client.get("/auth/devices", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200


def test_generate_requires_issuing_authority_role(client, admin_token):
    """A system_admin (not issuing_authority) must not be able to issue documents."""
    r = client.post(
        "/generate/passport",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"fields": {"surname": "Test"}},
    )
    assert r.status_code in (401, 403)
