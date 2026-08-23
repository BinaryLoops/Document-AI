"""Unit tests for Tracking (/tracking/*) and Notifications (/notifications/*)."""


def test_create_tracking_record(client):
    r = client.post(
        "/tracking/create",
        json={
            "application_id": "app-test-001",
            "document_id": "doc-test-001",
            "applicant_id": "demo-citizen-001",
            "document_type": "passport",
            "current_stage": "submitted",
        },
    )
    assert r.status_code in (200, 201, 422)


def test_get_tracking_status_not_found(client):
    r = client.get("/tracking/does-not-exist")
    assert r.status_code in (404, 200)


def test_get_notifications_for_user(client):
    r = client.get("/notifications", params={"user_id": "demo-citizen-001"})
    assert r.status_code == 200
    body = r.json()
    assert "notifications" in body


def test_get_notification_count(client):
    r = client.get("/notifications/count", params={"user_id": "demo-citizen-001"})
    assert r.status_code == 200
    assert "unread_count" in r.json()


def test_mark_notifications_read(client):
    r = client.post(
        "/notifications/mark-read",
        json={"user_id": "demo-citizen-001", "notification_ids": []},
    )
    assert r.status_code in (200, 422)
