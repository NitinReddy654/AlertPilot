from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Severity = Literal["low", "medium", "high", "critical"]
IncidentStatus = Literal["open", "acknowledged", "resolved"]


class LoginRequest(BaseModel):
    email: str = Field(..., examples=["admin@alertpilot.local"])
    password: str = Field(..., min_length=4)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserContext(BaseModel):
    email: str
    role: str


class AlertIn(BaseModel):
    source: str = Field(..., examples=["prometheus"])
    title: str = Field(..., examples=["Checkout API p95 latency above SLO"])
    description: str = ""
    service: str = Field(..., examples=["checkout-api"])
    environment: str = Field("prod", examples=["prod"])
    metric_name: str | None = Field(None, examples=["http_request_duration_seconds_p95"])
    metric_value: float | None = Field(None, examples=[1.8])
    threshold: float | None = Field(None, examples=[0.75])
    labels: dict[str, str] = Field(default_factory=dict)


class ServiceIn(BaseModel):
    name: str
    owner_team: str
    tier: int = Field(ge=0, le=3)
    runbook_url: str
    escalation_minutes: int = Field(ge=1, le=240)


class ServiceOut(ServiceIn):
    created_at: str


class IncidentOut(BaseModel):
    id: str
    fingerprint: str
    title: str
    service: str
    environment: str
    severity: Severity
    status: IncidentStatus
    owner_team: str
    runbook_url: str
    source: str
    summary: str
    occurrences: int
    first_seen: str
    last_seen: str
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    resolved_at: str | None = None
    resolved_by: str | None = None


class IncidentDetail(IncidentOut):
    events: list[dict[str, Any]]


class IncidentActionResponse(BaseModel):
    incident: IncidentOut
    message: str


class SummaryResponse(BaseModel):
    open: int
    acknowledged: int
    resolved: int
    critical_open: int
    high_open: int
    total_occurrences: int

