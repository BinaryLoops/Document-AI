"""
Unit tests for the Verification Engine (/verify/*) and the Document
Generation Engine (/generate/*, /generated/*).
"""
import uuid


def test_verify_document_requires_document_id(client):
    r = client.post("/verify/document", json={"ocr_text": "sample"})
    assert r.status_code in (400, 422)


def test_verify_document_full_pipeline(client):
    r = client.post(
        "/verify/document",
        json={
            "document_id": f"test-{uuid.uuid4()}",
            "ocr_text": "Government of India Birth Certificate Ravi Kumar",
            "document_type": "birth_certificate",
            "owner": "demo-citizen-001",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["verification"]["trust_badge"] in ("green", "yellow", "red")


def test_list_verification_departments(client):
    r = client.get("/verify/departments")
    assert r.status_code == 200
    assert len(r.json()["departments"]) > 0


def test_generate_template_schema(client):
    r = client.get("/generate/template/passport")
    assert r.status_code == 200
    body = r.json()
    assert body["document_type"] == "passport"
    required_fields = {f["name"] for f in body["fields"] if f["required"]}
    assert "surname" in required_fields


def test_generate_public_key_available(client):
    r = client.get("/generate/pubkey")
    assert r.status_code == 200
    assert "BEGIN PUBLIC KEY" in r.json()["public_key_pem"]


def test_generate_requires_authentication(client):
    r = client.post("/generate/passport", json={"fields": {}})
    assert r.status_code in (401, 403)


def test_generate_rejects_incomplete_fields(client, issuing_authority_token):
    r = client.post(
        "/generate/passport",
        headers={"Authorization": f"Bearer {issuing_authority_token}"},
        json={"fields": {"surname": "OnlyOneField"}},
    )
    assert r.status_code == 422
    assert "errors" in r.json()["detail"]


def test_generate_and_download_passport_end_to_end(client, issuing_authority_token):
    r = client.post(
        "/generate/passport",
        headers={"Authorization": f"Bearer {issuing_authority_token}"},
        json={
            "applicant_user_id": f"perf-test-{uuid.uuid4().hex[:8]}",
            "fields": {
                "surname": "Kumar", "given_names": "Test",
                "date_of_birth": "1990-01-12", "place_of_birth": "Pune",
                "gender": "M", "nationality": "Indian",
                "aadhaar_number": "999988887777", "father_name": "Test Father",
                "mother_name": "Test Mother", "address": "1 Test Street, Pune",
                "application_type": "Fresh",
            },
        },
    )
    assert r.status_code in (200, 201)
    doc_id = r.json()["document_id"]

    dl = client.get(f"/generated/{doc_id}", headers={"Authorization": f"Bearer {issuing_authority_token}"})
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/pdf"
    assert dl.content.startswith(b"%PDF")
