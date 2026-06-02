from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

from .cache import RedisCache
from .database import Database, utc_now
from .schemas import AlertIn, IncidentOut, ServiceIn, ServiceOut, SummaryResponse


SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
CRITICAL_KEYWORDS = {"outage", "unavailable", "down", "data loss", "payment failed"}
HIGH_KEYWORDS = {"latency", "error rate", "timeout", "slo", "degraded", "failure"}


def normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def fingerprint_alert(alert: AlertIn) -> str:
    normalized_title = normalize_text(alert.title)
    raw = "|".join([alert.service.lower(), alert.environment.lower(), normalized_title])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def score_alert(alert: AlertIn, service: dict[str, Any]) -> str:
    text = f"{alert.title} {alert.description}".lower()
    ratio = 0.0
    if alert.metric_value is not None and alert.threshold:
        ratio = alert.metric_value / max(alert.threshold, 1e-9)

    tier = int(service.get("tier", 2))
    is_prod = alert.environment.lower() in {"prod", "production"}

    if any(keyword in text for keyword in CRITICAL_KEYWORDS):
        return "critical" if is_prod else "high"
    if is_prod and (ratio >= 2.5 or tier == 0 and ratio >= 1.5):
        return "critical"
    if any(keyword in text for keyword in HIGH_KEYWORDS) or ratio >= 1.25:
        return "high" if is_prod else "medium"
    if is_prod or tier <= 1:
        return "medium"
    return "low"


def summarize_alert(alert: AlertIn, severity: str, service: dict[str, Any]) -> str:
    owner = service["owner_team"]
    if alert.metric_name and alert.metric_value is not None:
        return (
            f"{severity.upper()} alert for {alert.service}: {alert.metric_name}="
            f"{alert.metric_value} in {alert.environment}. Routed to {owner}."
        )
    return f"{severity.upper()} alert for {alert.service} in {alert.environment}. Routed to {owner}."


class IncidentService:
    def __init__(self, db: Database, cache: RedisCache | None = None, fingerprint_cache_ttl_seconds: int = 60):
        self.db = db
        self.cache = cache
        self.fingerprint_cache_ttl_seconds = fingerprint_cache_ttl_seconds

    def upsert_service(self, item: ServiceIn) -> ServiceOut:
        now = utc_now()
        self.db.execute(
            """
            INSERT INTO services(name, owner_team, tier, runbook_url, escalation_minutes, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                owner_team=excluded.owner_team,
                tier=excluded.tier,
                runbook_url=excluded.runbook_url,
                escalation_minutes=excluded.escalation_minutes
            """,
            (item.name, item.owner_team, item.tier, item.runbook_url, item.escalation_minutes, now),
        )
        row = self.db.query_one("SELECT * FROM services WHERE name = ?", (item.name,))
        return ServiceOut(**row)

    def list_services(self) -> list[ServiceOut]:
        rows = self.db.query_all("SELECT * FROM services ORDER BY tier ASC, name ASC")
        return [ServiceOut(**row) for row in rows]

    def ingest(self, alert: AlertIn, actor: str) -> IncidentOut:
        service = self.db.query_one("SELECT * FROM services WHERE name = ?", (alert.service,))
        if service is None:
            service = self._create_unknown_service(alert.service)

        fingerprint = fingerprint_alert(alert)
        severity = score_alert(alert, service)
        existing = None
        cached_incident_id = self.cache.get_fingerprint(fingerprint) if self.cache else None
        if cached_incident_id:
            existing = self.db.query_one(
                """
                SELECT * FROM incidents
                WHERE id = ? AND status IN ('open', 'acknowledged')
                LIMIT 1
                """,
                (cached_incident_id,),
            )
        if existing is None:
            existing = self.db.query_one(
                """
                SELECT * FROM incidents
                WHERE fingerprint = ? AND status IN ('open', 'acknowledged')
                ORDER BY last_seen DESC
                LIMIT 1
                """,
                (fingerprint,),
            )
            if existing and self.cache:
                self.cache.set_fingerprint(fingerprint, existing["id"], self.fingerprint_cache_ttl_seconds)
        payload = alert.model_dump()
        now = utc_now()

        if existing:
            new_severity = self._max_severity(existing["severity"], severity)
            self.db.execute(
                """
                UPDATE incidents
                SET occurrences = occurrences + 1,
                    last_seen = ?,
                    severity = ?,
                    summary = ?
                WHERE id = ?
                """,
                (now, new_severity, summarize_alert(alert, new_severity, service), existing["id"]),
            )
            self._append_event(existing["id"], "deduplicated_alert", payload)
            self.db.audit(actor, "alert.deduplicated", existing["id"], {"fingerprint": fingerprint})
            if self.cache:
                self.cache.set_fingerprint(fingerprint, existing["id"], self.fingerprint_cache_ttl_seconds)
            updated = self.get_incident(existing["id"])
            return IncidentOut(**{k: updated[k] for k in IncidentOut.model_fields})

        incident_id = str(uuid.uuid4())
        summary = summarize_alert(alert, severity, service)
        self.db.execute(
            """
            INSERT INTO incidents(
                id, fingerprint, title, service, environment, severity, status, owner_team,
                runbook_url, source, summary, occurrences, first_seen, last_seen, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (
                incident_id,
                fingerprint,
                alert.title,
                alert.service,
                alert.environment,
                severity,
                service["owner_team"],
                service["runbook_url"],
                alert.source,
                summary,
                now,
                now,
                actor,
            ),
        )
        self._append_event(incident_id, "alert_created_incident", payload)
        self.db.audit(actor, "incident.created", incident_id, {"severity": severity})
        if self.cache:
            self.cache.set_fingerprint(fingerprint, incident_id, self.fingerprint_cache_ttl_seconds)
        return IncidentOut(**self.get_incident(incident_id))

    def list_incidents(self, status: str | None = None, limit: int = 50) -> list[IncidentOut]:
        if status:
            rows = self.db.query_all(
                "SELECT * FROM incidents WHERE status = ? ORDER BY last_seen DESC LIMIT ?",
                (status, limit),
            )
        else:
            rows = self.db.query_all("SELECT * FROM incidents ORDER BY last_seen DESC LIMIT ?", (limit,))
        return [IncidentOut(**row) for row in rows]

    def get_incident(self, incident_id: str) -> dict[str, Any]:
        row = self.db.query_one("SELECT * FROM incidents WHERE id = ?", (incident_id,))
        if row is None:
            raise KeyError(incident_id)
        return row

    def get_detail(self, incident_id: str) -> dict[str, Any]:
        row = self.get_incident(incident_id)
        events = self.db.query_all(
            "SELECT event_type, payload, created_at FROM incident_events WHERE incident_id = ? ORDER BY created_at ASC",
            (incident_id,),
        )
        row["events"] = [
            {**event, "payload": json.loads(event["payload"])}
            for event in events
        ]
        return row

    def acknowledge(self, incident_id: str, actor: str) -> IncidentOut:
        now = utc_now()
        self.get_incident(incident_id)
        self.db.execute(
            """
            UPDATE incidents
            SET status = 'acknowledged', acknowledged_at = ?, acknowledged_by = ?
            WHERE id = ? AND status != 'resolved'
            """,
            (now, actor, incident_id),
        )
        self._append_event(incident_id, "incident_acknowledged", {"actor": actor})
        self.db.audit(actor, "incident.acknowledged", incident_id)
        return IncidentOut(**self.get_incident(incident_id))

    def resolve(self, incident_id: str, actor: str) -> IncidentOut:
        now = utc_now()
        self.get_incident(incident_id)
        self.db.execute(
            """
            UPDATE incidents
            SET status = 'resolved', resolved_at = ?, resolved_by = ?
            WHERE id = ?
            """,
            (now, actor, incident_id),
        )
        self._append_event(incident_id, "incident_resolved", {"actor": actor})
        self.db.audit(actor, "incident.resolved", incident_id)
        return IncidentOut(**self.get_incident(incident_id))

    def summary(self) -> SummaryResponse:
        rows = self.db.query_all("SELECT status, severity, occurrences FROM incidents")
        counts = {"open": 0, "acknowledged": 0, "resolved": 0}
        critical_open = 0
        high_open = 0
        total_occurrences = 0
        for row in rows:
            counts[row["status"]] += 1
            total_occurrences += row["occurrences"]
            if row["status"] in {"open", "acknowledged"} and row["severity"] == "critical":
                critical_open += 1
            if row["status"] in {"open", "acknowledged"} and row["severity"] == "high":
                high_open += 1
        return SummaryResponse(
            open=counts["open"],
            acknowledged=counts["acknowledged"],
            resolved=counts["resolved"],
            critical_open=critical_open,
            high_open=high_open,
            total_occurrences=total_occurrences,
        )

    def _append_event(self, incident_id: str, event_type: str, payload: dict[str, Any]) -> None:
        self.db.execute(
            """
            INSERT INTO incident_events(id, incident_id, event_type, payload, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), incident_id, event_type, json.dumps(payload), utc_now()),
        )

    def _create_unknown_service(self, service_name: str) -> dict[str, Any]:
        fallback = ServiceIn(
            name=service_name,
            owner_team="platform-triage",
            tier=2,
            runbook_url="https://runbooks.local/platform-triage",
            escalation_minutes=30,
        )
        return self.upsert_service(fallback).model_dump()

    def _max_severity(self, current: str, candidate: str) -> str:
        return current if SEVERITY_RANK[current] >= SEVERITY_RANK[candidate] else candidate

