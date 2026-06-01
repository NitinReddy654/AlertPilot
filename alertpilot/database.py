from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import Settings
from .security import hash_password


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.RLock()
        self._connection = self._connect(settings.database_path)

    def _connect(self, path: str) -> sqlite3.Connection:
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize(self) -> None:
        with self._lock:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    email TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS services (
                    name TEXT PRIMARY KEY,
                    owner_team TEXT NOT NULL,
                    tier INTEGER NOT NULL,
                    runbook_url TEXT NOT NULL,
                    escalation_minutes INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    fingerprint TEXT NOT NULL,
                    title TEXT NOT NULL,
                    service TEXT NOT NULL,
                    environment TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    owner_team TEXT NOT NULL,
                    runbook_url TEXT NOT NULL,
                    source TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    occurrences INTEGER NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    acknowledged_at TEXT,
                    acknowledged_by TEXT,
                    resolved_at TEXT,
                    resolved_by TEXT,
                    created_by TEXT NOT NULL,
                    FOREIGN KEY(service) REFERENCES services(name)
                );

                CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
                CREATE INDEX IF NOT EXISTS idx_incidents_fingerprint_status
                    ON incidents(fingerprint, status);

                CREATE TABLE IF NOT EXISTS incident_events (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(incident_id) REFERENCES incidents(id)
                );

                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._seed_defaults()
            self._connection.commit()

    def _seed_defaults(self) -> None:
        self.execute(
            """
            INSERT OR IGNORE INTO users(email, password_hash, role, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                self.settings.bootstrap_email,
                hash_password(self.settings.bootstrap_password),
                "admin",
                utc_now(),
            ),
        )
        services = [
            ("checkout-api", "payments-platform", 0, "https://runbooks.local/checkout-api", 10),
            ("identity-api", "security-platform", 0, "https://runbooks.local/identity-api", 10),
            ("search-api", "discovery", 1, "https://runbooks.local/search-api", 20),
            ("email-worker", "growth-platform", 2, "https://runbooks.local/email-worker", 45),
        ]
        for service in services:
            self.execute(
                """
                INSERT OR IGNORE INTO services(
                    name, owner_team, tier, runbook_url, escalation_minutes, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (*service, utc_now()),
            )

    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            cursor = self._connection.execute(sql, tuple(params))
            self._connection.commit()
            return cursor

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._connection.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None

    def query_all(self, sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def audit(self, actor: str, action: str, target_id: str, metadata: dict[str, Any] | None = None) -> None:
        self.execute(
            """
            INSERT INTO audit_logs(id, actor, action, target_id, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), actor, action, target_id, json.dumps(metadata or {}), utc_now()),
        )

    def close(self) -> None:
        with self._lock:
            self._connection.close()

