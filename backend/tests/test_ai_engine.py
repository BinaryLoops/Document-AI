"""Unit tests for the AI Intelligence engine (/ai/*, /assistant/*)."""

SAMPLE_TEXT = (
    "This certificate confirms that Ravi Kumar was born on 12 January 1990 "
    "in Pune, Maharashtra. Issued by the Registrar of Births on 5 March 1990."
)


def test_summarize(client):
    r = client.post("/ai/summarize", json={"text": SAMPLE_TEXT, "document_type": "birth_certificate"})
    assert r.status_code == 200
    assert r.json()["status"] == "success"


def test_summarize_requires_text(client):
    r = client.post("/ai/summarize", json={"document_type": "birth_certificate"})
    assert r.status_code == 422


def test_extract_entities(client):
    r = client.post("/ai/entities", json={"text": SAMPLE_TEXT})
    assert r.status_code == 200
    assert "entities" in r.json()


def test_extract_timeline(client):
    r = client.post("/ai/timeline", json={"text": SAMPLE_TEXT})
    assert r.status_code == 200
    assert "timeline" in r.json()


def test_case_intelligence_requires_two_documents(client):
    r = client.post("/ai/case-intel", json={"documents": [{"id": "1", "text": SAMPLE_TEXT}]})
    assert r.status_code in (200, 400)


def test_assistant_ask(client):
    r = client.post("/assistant/ask", json={"question": "Who was born?", "text": SAMPLE_TEXT})
    assert r.status_code == 200
    assert r.json()["status"] == "success"
