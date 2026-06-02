from alertpilot.events.schemas import IncidentCreatedEvent
from alertpilot.schemas import IncidentOut


def test_incident_created_event_from_incident():
    incident = IncidentOut(
        id="incident-1",
        fingerprint="fingerprint",
        title="checkout outage",
        service="checkout-api",
        environment="prod",
        severity="critical",
        status="open",
        owner_team="payments-platform",
        runbook_url="https://runbooks.local/checkout-api",
        source="prometheus",
        summary="summary",
        occurrences=1,
        first_seen="2026-01-01T00:00:00+00:00",
        last_seen="2026-01-01T00:00:00+00:00",
    )
    event = IncidentCreatedEvent.from_incident(incident)
    assert event.event_type == "incident.created"
    assert event.incident_id == "incident-1"
    assert event.severity == "critical"
