import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alertpilot.config import Settings
from alertpilot.main import create_app


@pytest.fixture
def app_client():
    tmp = tempfile.TemporaryDirectory()
    settings = Settings(
        database_path=str(Path(tmp.name) / "test.db"),
        token_secret="test-secret",
        enable_redis=False,
        enable_kafka=False,
    )
    client = TestClient(create_app(settings))
    try:
        yield client
    finally:
        client.close()
        tmp.cleanup()


@pytest.fixture
def rate_limited_client():
    tmp = tempfile.TemporaryDirectory()
    settings = Settings(
        database_path=str(Path(tmp.name) / "limited.db"),
        token_secret="test-secret",
        enable_redis=True,
        enable_kafka=False,
        alert_rate_limit_per_minute=2,
        alert_rate_limit_window_seconds=60,
    )
    client = TestClient(create_app(settings))
    try:
        yield client
    finally:
        client.close()
        tmp.cleanup()


@pytest.fixture
def auth_headers(app_client: TestClient):
    response = app_client.post("/v1/auth/login", json={"email": "admin@alertpilot.local", "password": "changeme"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def limited_auth_headers(rate_limited_client: TestClient):
    response = rate_limited_client.post("/v1/auth/login", json={"email": "admin@alertpilot.local", "password": "changeme"})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def alert_payload():
    return {
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
