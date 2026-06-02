def test_incident_acknowledge_and_resolve(app_client, auth_headers, alert_payload):
    created = app_client.post("/v1/alerts", json=alert_payload, headers=auth_headers).json()
    ack = app_client.post(f"/v1/incidents/{created['id']}/ack", headers=auth_headers)
    assert ack.status_code == 200
    assert ack.json()["incident"]["status"] == "acknowledged"
    resolved = app_client.post(f"/v1/incidents/{created['id']}/resolve", headers=auth_headers)
    assert resolved.status_code == 200
    assert resolved.json()["incident"]["status"] == "resolved"


def test_incident_detail_includes_event_timeline(app_client, auth_headers, alert_payload):
    created = app_client.post("/v1/alerts", json=alert_payload, headers=auth_headers).json()
    detail = app_client.get(f"/v1/incidents/{created['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["events"][0]["event_type"] == "alert_created_incident"


def test_missing_incident_returns_404(app_client, auth_headers):
    response = app_client.get("/v1/incidents/missing", headers=auth_headers)
    assert response.status_code == 404
