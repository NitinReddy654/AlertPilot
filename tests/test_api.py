import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from alertpilot.config import Settings
from alertpilot.main import create_app


def make_client():
    tmp = tempfile.TemporaryDirectory()
    app = create_app(Settings(database_path=str(Path(tmp.name) / "test.db"), token_secret="test-secret"))
    return TestClient(app), tmp


def auth_headers(client: TestClient):
    response = client.post("/v1/auth/login", json={"email": "admin@alertpilot.local", "password": "changeme"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_health_and_auth_flow():
    client, tmp = make_client()
    try:
        assert client.get("/health").json()["status"] == "ok"
        headers = auth_headers(client)
        services = client.get("/v1/services", headers=headers)
        assert services.status_code == 200
        assert len(services.json()) >= 1
    finally:
        tmp.cleanup()


def test_alert_ingestion_deduplicates_incidents():
    client, tmp = make_client()
    try:
        headers = auth_headers(client)
        payload = {
            "source": "prometheus",
            "title": "checkout-api p95 latency above SLO",
            "description": "SLO burn alert",
            "service": "checkout-api",
            "environment": "prod",
            "metric_name": "latency_p95",
            "metric_value": 1.7,
            "threshold": 0.75,
            "labels": {"region": "us-east-1"},
        }
        first = client.post("/v1/alerts", json=payload, headers=headers)
        second = client.post("/v1/alerts", json=payload, headers=headers)
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["id"] == second.json()["id"]
        assert second.json()["occurrences"] == 2
        ack = client.post(f"/v1/incidents/{first.json()['id']}/ack", headers=headers)
        assert ack.json()["incident"]["status"] == "acknowledged"
        metrics = client.get("/metrics")
        assert "alertpilot_http_requests_total" in metrics.text
    finally:
        tmp.cleanup()
