def test_duplicate_alert_increments_occurrence_count(app_client, auth_headers, alert_payload):
    first = app_client.post("/v1/alerts", json=alert_payload, headers=auth_headers)
    second = app_client.post("/v1/alerts", json=alert_payload, headers=auth_headers)
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["occurrences"] == 2


def test_deduplication_preserves_highest_severity(app_client, auth_headers, alert_payload):
    medium_payload = {**alert_payload, "title": "checkout queue depth", "metric_value": 0.8, "threshold": 1.0}
    critical_payload = {**medium_payload, "title": "checkout queue depth", "description": "payment failed"}
    first = app_client.post("/v1/alerts", json=medium_payload, headers=auth_headers).json()
    second = app_client.post("/v1/alerts", json=critical_payload, headers=auth_headers).json()
    assert first["id"] == second["id"]
    assert second["severity"] == "critical"


def test_list_incidents_status_filter(app_client, auth_headers, alert_payload):
    created = app_client.post("/v1/alerts", json=alert_payload, headers=auth_headers).json()
    app_client.post(f"/v1/incidents/{created['id']}/ack", headers=auth_headers)
    acknowledged = app_client.get("/v1/incidents?status=acknowledged", headers=auth_headers)
    assert acknowledged.status_code == 200
    assert len(acknowledged.json()) == 1
