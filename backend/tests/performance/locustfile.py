"""
Locust load-testing scenarios for the DocuMind AI backend.

Install:
    pip install -r requirements-dev.txt

Run (headless, 50 users, ramp 5/s, 2 minutes) against a running server:
    locust -f tests/performance/locustfile.py --host http://localhost:8000 \
           --headless -u 50 -r 5 -t 2m --csv=perf_report

Run with the interactive web UI instead:
    locust -f tests/performance/locustfile.py --host http://localhost:8000
    # then open http://localhost:8089

NOTE: run this against a real `uvicorn main:app` process (not TestClient) --
Locust drives HTTP over the network to measure realistic latency/throughput.
"""
import random
import uuid

from locust import HttpUser, task, between


class ReadOnlyBrowsingUser(HttpUser):
    """Simulates a citizen/official browsing dashboards -- mostly GETs."""

    weight = 3
    wait_time = between(0.5, 2.0)

    @task(5)
    def health(self):
        self.client.get("/health", name="/health")

    @task(3)
    def status(self):
        self.client.get("/status", name="/status")

    @task(2)
    def graph_stats(self):
        self.client.get("/graph/stats", name="/graph/stats")

    @task(2)
    def verification_departments(self):
        self.client.get("/verify/departments", name="/verify/departments")

    @task(1)
    def openapi_schema(self):
        self.client.get("/openapi.json", name="/openapi.json")


class AIWorkloadUser(HttpUser):
    """Simulates AI Intelligence usage -- CPU-heavier POST workloads."""

    weight = 2
    wait_time = between(1.0, 3.0)

    SAMPLE_TEXT = (
        "This certificate confirms that a citizen was born in Pune, "
        "Maharashtra. Issued by the Registrar of Births."
    )

    @task(3)
    def summarize(self):
        self.client.post(
            "/ai/summarize",
            json={"text": self.SAMPLE_TEXT, "document_type": "birth_certificate"},
            name="/ai/summarize",
        )

    @task(2)
    def entities(self):
        self.client.post("/ai/entities", json={"text": self.SAMPLE_TEXT}, name="/ai/entities")

    @task(1)
    def assistant_ask(self):
        self.client.post(
            "/assistant/ask",
            json={"question": "Where was the citizen born?", "text": self.SAMPLE_TEXT},
            name="/assistant/ask",
        )


class VerificationWorkloadUser(HttpUser):
    """Simulates the 12-step verification pipeline under load."""

    weight = 1
    wait_time = between(1.0, 4.0)

    @task
    def verify_document(self):
        doc_id = f"perf-{uuid.uuid4().hex[:10]}"
        self.client.post(
            "/verify/document",
            json={
                "document_id": doc_id,
                "ocr_text": "Government of India Sample Document",
                "document_type": random.choice(
                    ["identity_proof", "birth_certificate", "income_certificate"]
                ),
                "owner": "perf-test-user",
            },
            name="/verify/document",
        )
