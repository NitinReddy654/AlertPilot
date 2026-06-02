def test_post_alert_requires_auth(app_client, alert_payload):
    response = app_client.post("/v1/alerts", json=alert_payload)
    assert response.status_code == 401


def test_post_alert_creates_incident(app_client, auth_headers, alert_payload):
    response = app_client.post("/v1/alerts", json=alert_payload, headers=auth_headers)
    assert response.status_code == 201
    body = response.json()
    assert body["service"] == "checkout-api"
    assert body["severity"] == "critical"
    assert body["occurrences"] == 1


def test_post_alert_rate_limit_returns_429(rate_limited_client, limited_auth_headers, alert_payload):
    assert rate_limited_client.post("/v1/alerts", json=alert_payload, headers=limited_auth_headers).status_code == 201
    assert rate_limited_client.post("/v1/alerts", json={**alert_payload, "title": "checkout-api timeout"}, headers=limited_auth_headers).status_code == 201
    blocked = rate_limited_client.post("/v1/alerts", json={**alert_payload, "title": "checkout-api outage"}, headers=limited_auth_headers)
    assert blocked.status_code == 429
    assert blocked.json()["limit"] == 2


def test_invalid_login_rejected(app_client):
    response = app_client.post("/v1/auth/login", json={"email": "admin@alertpilot.local", "password": "wrong"})
    assert response.status_code == 401


def test_summary_reflects_alert_ingestion(app_client, auth_headers, alert_payload):
    app_client.post("/v1/alerts", json=alert_payload, headers=auth_headers)
    summary = app_client.get("/v1/summary", headers=auth_headers)
    assert summary.status_code == 200
    assert summary.json()["open"] == 1
    assert summary.json()["critical_open"] == 1
