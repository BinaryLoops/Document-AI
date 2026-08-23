"""
Unit tests for the RAG subsystem (/documents, /query, /search).

These exercise the real embedding model + FAISS vector DB when the heavy
ML dependencies (torch, sentence-transformers, faiss-cpu) are installed.
If they are missing, the RAG engine starts in degraded mode and these
tests are skipped automatically.
"""
import pytest


def _rag_available(client) -> bool:
    return client.get("/status").json()["components"]["rag_engine"] == "ready"


@pytest.fixture(autouse=True)
def _skip_if_rag_unavailable(client):
    if not _rag_available(client):
        pytest.skip("RAG engine not initialised (torch/faiss/sentence-transformers not installed)")


def test_ingest_document(client):
    r = client.post(
        "/documents",
        json={"documents": [{"title": "Test Doc", "text": "FastAPI is a modern Python web framework."}]},
    )
    assert r.status_code == 200
    assert len(r.json()["document_ids"]) == 1


def test_query_returns_json_serializable_scores(client):
    client.post(
        "/documents",
        json={"documents": [{"title": "RTI", "text": "The Right to Information Act empowers citizens."}]},
    )
    r = client.post("/query", json={"query": "What does the RTI Act do?", "top_k": 3})
    assert r.status_code == 200
    body = r.json()
    assert "response" in body


def test_search_endpoint_no_numpy_leak(client):
    """
    Regression test: storage/vector_db.py used to return numpy.float32 scores
    which are not JSON-serializable via FastAPI's jsonable_encoder, causing
    a 500 error on any non-empty result set.
    """
    client.post(
        "/documents",
        json={"documents": [{"title": "Doc A", "text": "Artificial intelligence and machine learning."}]},
    )
    r = client.get("/search", params={"query": "machine learning"})
    assert r.status_code == 200
    for result in r.json()["results"]:
        assert isinstance(result["score"], float)


def test_search_missing_query_param_returns_422(client):
    r = client.get("/search")
    assert r.status_code == 422
