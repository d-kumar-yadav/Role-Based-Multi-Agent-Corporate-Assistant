from dotenv import load_dotenv
load_dotenv()

from fastapi.testclient import TestClient
from app.main import app
from app.observability.metrics import get_metrics

client = TestClient(app)


def _login(email: str, password: str = "password123") -> str:
    r = client.post("/auth/token", data={"username": email, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_metrics_json_endpoint_returns_dict():
    r = client.get("/metrics")
    assert r.status_code == 200
    data = r.json()
    assert "total_requests" in data
    assert "blocked_count" in data
    assert "latency_ms" in data


def test_metrics_prometheus_returns_text():
    r = client.get("/metrics/prometheus")
    assert r.status_code == 200
    text = r.text
    assert "copilot_requests_total" in text
    assert "# HELP" in text
    assert "# TYPE" in text


def test_metrics_window_filter():
    r = client.get("/metrics", params={"window": "1h"})
    assert r.status_code == 200
    assert r.json()["window"] == "1h"


def test_successful_query_records_metric():
    # Count before
    before = client.get("/metrics?window=all").json()["total_requests"]

    # Send a request that will hit a dialog path (fails safe without Groq)
    token = _login("alice.johnson@meridianglobal.example")
    r = client.post(
        "/query",
        json={"query": "hello", "thread_id": "test-obs-1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200

    # Count after
    after = client.get("/metrics?window=all").json()["total_requests"]
    assert after >= before + 1


def test_audit_log_chain_valid_after_requests():
    from app.observability.logger import verify_chain
    result = verify_chain()
    assert result["valid"] is True


def test_response_has_request_id_header():
    token = _login("alice.johnson@meridianglobal.example")
    r = client.post(
        "/query",
        json={"query": "hello", "thread_id": "test-obs-2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert "X-Request-ID" in r.headers

