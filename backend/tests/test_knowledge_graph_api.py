"""Unit tests for the Government Knowledge Graph API (/graph/*)."""


def test_graph_stats(client):
    r = client.get("/graph/stats")
    assert r.status_code == 200
    assert "stats" in r.json()


def test_graph_export(client):
    r = client.get("/graph/export")
    assert r.status_code == 200
    assert "graph" in r.json()


def test_graph_departments(client):
    r = client.get("/graph/departments")
    assert r.status_code == 200


def test_graph_ingest_and_query_document(client):
    r = client.post(
        "/graph/ingest",
        json={
            "document_id": "kg-test-doc-1",
            "document_name": "Birth Certificate - Ravi Kumar",
            "document_type": "birth_certificate",
            "owner": "Ravi Kumar",
        },
    )
    assert r.status_code == 200

    r2 = client.get("/graph/document/kg-test-doc-1")
    assert r2.status_code == 200


def test_fraud_clusters_endpoint(client):
    r = client.get("/graph/fraud-clusters")
    assert r.status_code == 200


def test_duplicate_identity_detection_endpoint(client):
    r = client.get("/graph/duplicates")
    assert r.status_code == 200
