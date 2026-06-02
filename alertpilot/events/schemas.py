from __future__ import annotations

from pydantic import BaseModel

from alertpilot.schemas import IncidentOut, Severity


class IncidentCreatedEvent(BaseModel):
    event_type: str = "incident.created"
    incident_id: str
    fingerprint: str
    title: str
    service: str
    environment: str
    severity: Severity
    owner_team: str
    runbook_url: str
    source: str
    occurrence_count: int

    @classmethod
    def from_incident(cls, incident: IncidentOut) -> "IncidentCreatedEvent":
        return cls(
            incident_id=incident.id,
            fingerprint=incident.fingerprint,
            title=incident.title,
            service=incident.service,
            environment=incident.environment,
            severity=incident.severity,
            owner_team=incident.owner_team,
            runbook_url=incident.runbook_url,
            source=incident.source,
            occurrence_count=incident.occurrences,
        )
