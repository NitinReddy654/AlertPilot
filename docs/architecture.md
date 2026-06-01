# AlertPilot Architecture

AlertPilot separates runtime incident operations from offline model experimentation. The runtime API is deterministic and low-latency, while the DVC path validates data and trains severity prediction models that can later be promoted into online scoring.

## Product Boundary

AlertPilot is an incident triage platform for SRE, DevOps, and platform engineering teams. The core workflow is operational: alerts arrive, repeated signals collapse into one incident, severity is calculated, ownership is routed, responders acknowledge and resolve, and metrics expose system health.

## Runtime Path

1. A monitoring tool sends an alert to `/v1/alerts`.
2. FastAPI validates the payload with Pydantic and authenticates the bearer token.
3. The triage engine computes a normalized fingerprint from service, environment, and title.
4. If an open incident already has the same fingerprint, the occurrence count is incremented.
5. Otherwise, a new incident is created with severity, owner team, service tier, and runbook context.
6. Audit events record incident creation, acknowledgement, and resolution.
7. Prometheus counters and histograms are updated for operational visibility.

## Offline Path

1. Synthetic production-like alerts are generated with deterministic random seeds.
2. Great Expectations validates schema, enums, non-null columns, and numeric ranges.
3. scikit-learn trains a severity classifier on validated alert records.
4. MLflow records metrics, parameters, and artifacts.
5. DVC locks data, model, metric, and benchmark outputs for reproducibility.
6. Benchmark scripts measure API ingestion throughput, latency percentiles, and deduplication behavior.

## Data Model

| Entity | Purpose |
| --- | --- |
| `users` | Bootstrap admin account and role-based authorization |
| `services` | Service catalog with owner team, tier, runbook, and escalation window |
| `incidents` | Deduplicated operational incidents with severity, status, occurrence count, and fingerprint |
| `incident_events` | Timeline events for created, deduplicated, acknowledged, and resolved actions |
| `audit_logs` | Security and operational audit trail |

## Reliability and Security Decisions

- Deterministic fingerprinting keeps ingestion fast and explainable for responders.
- Severity combines service tier, environment, threshold ratio, and keyword signals so the online path does not depend on model availability.
- PBKDF2 password hashing and HMAC bearer tokens avoid storing plaintext credentials or relying on hard-coded API keys.
- Admin-only service catalog writes separate operational configuration from ordinary incident response actions.
- Prometheus metrics and structured JSON logs support production-style debugging and monitoring.
- DVC and Great Expectations make the ML/data pipeline reproducible from source instead of requiring committed generated datasets.

## Scaling Path

SQLite keeps the project portable for local execution and automated verification, while the module boundaries are intentionally shaped for production migration:

- Replace SQLite with Postgres while keeping the repository-style `Database` interface.
- Move optional Redis counters into distributed fingerprint locks for high-concurrency ingestion.
- Promote the trained severity classifier behind a feature flag after shadow evaluation.
- Add OpenTelemetry traces alongside the existing Prometheus metrics.
- Deploy the API behind a managed container platform with external secrets and managed observability.

## Operational Guarantees

| Concern | Approach |
| --- | --- |
| Ingestion availability | Incident creation uses deterministic scoring and does not require an online ML dependency. |
| Duplicate suppression | Open incidents are matched through stable fingerprints derived from normalized alert context. |
| Auditability | Security and incident lifecycle actions are written to audit and event tables. |
| Reproducibility | DVC locks the data generation, validation, training, and benchmark pipeline stages. |
| Observability | Prometheus metrics, structured request logs, health checks, and readiness checks expose runtime state. |
| Deployment portability | Docker and Compose provide a repeatable local deployment with Redis, Prometheus, and Grafana. |

## Measured Verification

- Unit/API/security/contract tests: 7 passed.
- Dataset generation and validation: 5,000 alerts.
- Severity classifier: 0.697 accuracy and 0.701 weighted F1.
- API benchmark: 750 requests at 600.14 requests/sec, 2.525 ms p95 latency, 3.812 ms p99 latency.
