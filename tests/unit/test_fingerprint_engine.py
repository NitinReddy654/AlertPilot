import pytest

from alertpilot.schemas import AlertIn
from alertpilot.triage import fingerprint_alert, normalize_text


@pytest.mark.parametrize(
    ("title_a", "title_b"),
    [
        ("Checkout API p95 latency above SLO", "checkout-api: P95 LATENCY above SLO!!!"),
        ("Identity API Error Rate", "identity api error-rate"),
        ("Search API timeout", "search api timeout"),
        ("Payment failed in checkout", "payment failed in checkout"),
        ("Email Worker queue depth high", "email worker queue depth high"),
        ("API    unavailable", "api unavailable"),
        ("Region us-east-1 down", "region: us east 1 down"),
        ("Data Loss warning", "data loss warning"),
        ("SLO burn alert", "slo-burn-alert"),
        ("Cache hit ratio degraded", "cache hit ratio degraded!!!"),
    ],
)
def test_fingerprint_normalizes_equivalent_titles(title_a, title_b):
    first = AlertIn(source="prometheus", service="checkout-api", environment="prod", title=title_a)
    second = AlertIn(source="datadog", service="checkout-api", environment="prod", title=title_b)
    assert normalize_text(title_a) == normalize_text(title_b)
    assert fingerprint_alert(first) == fingerprint_alert(second)


def test_fingerprint_changes_by_service():
    first = AlertIn(source="prometheus", service="checkout-api", environment="prod", title="latency above SLO")
    second = AlertIn(source="prometheus", service="search-api", environment="prod", title="latency above SLO")
    assert fingerprint_alert(first) != fingerprint_alert(second)


def test_fingerprint_changes_by_environment():
    first = AlertIn(source="prometheus", service="checkout-api", environment="prod", title="latency above SLO")
    second = AlertIn(source="prometheus", service="checkout-api", environment="staging", title="latency above SLO")
    assert fingerprint_alert(first) != fingerprint_alert(second)
