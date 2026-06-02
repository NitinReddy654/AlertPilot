import pytest

from alertpilot.schemas import AlertIn
from alertpilot.triage import score_alert


@pytest.mark.parametrize(
    ("title", "environment", "tier", "metric_value", "threshold", "expected"),
    [
        ("checkout outage", "prod", 0, None, None, "critical"),
        ("checkout outage", "staging", 0, None, None, "high"),
        ("payment failed", "prod", 1, None, None, "critical"),
        ("api unavailable", "dev", 2, None, None, "high"),
        ("latency above slo", "prod", 0, 1.5, 0.75, "critical"),
        ("latency above slo", "prod", 2, 1.0, 0.75, "high"),
        ("timeout warning", "staging", 2, 1.0, 0.75, "medium"),
        ("queue depth", "prod", 2, 0.8, 1.0, "medium"),
        ("queue depth", "dev", 1, 0.8, 1.0, "medium"),
        ("queue depth", "dev", 3, 0.8, 1.0, "low"),
    ],
)
def test_score_alert_rules(title, environment, tier, metric_value, threshold, expected):
    alert = AlertIn(
        source="prometheus",
        service="checkout-api",
        environment=environment,
        title=title,
        metric_value=metric_value,
        threshold=threshold,
    )
    assert score_alert(alert, {"tier": tier, "owner_team": "platform", "runbook_url": "https://runbooks.local"}) == expected


def test_score_alert_uses_description_keywords():
    alert = AlertIn(
        source="prometheus",
        service="checkout-api",
        environment="prod",
        title="generic alert",
        description="service is degraded",
    )
    assert score_alert(alert, {"tier": 2, "owner_team": "platform", "runbook_url": "https://runbooks.local"}) == "high"
