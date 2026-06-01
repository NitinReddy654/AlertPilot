from alertpilot.schemas import AlertIn
from alertpilot.triage import fingerprint_alert, normalize_text, score_alert

SERVICE = {"tier": 0, "owner_team": "payments", "runbook_url": "https://runbooks.local/payments"}


def test_fingerprint_normalizes_alert_titles():
    first = AlertIn(source="prometheus", service="checkout-api", environment="prod", title="Checkout API p95 latency above SLO")
    second = AlertIn(source="datadog", service="checkout-api", environment="prod", title="checkout-api: P95 LATENCY above SLO!!!")
    assert normalize_text(first.title) == normalize_text(second.title)
    assert fingerprint_alert(first) == fingerprint_alert(second)


def test_severity_scoring_escalates_tier_zero_prod_alerts():
    alert = AlertIn(
        source="prometheus",
        service="checkout-api",
        environment="prod",
        title="checkout-api p95 latency above SLO",
        metric_name="latency_p95",
        metric_value=1.5,
        threshold=0.75,
    )
    assert score_alert(alert, SERVICE) == "critical"
