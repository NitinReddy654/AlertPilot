# AlertPilot Architecture

AlertPilot separates the online incident-response path from the offline data and model experimentation path. The online path stays deterministic and low-latency so alert ingestion can continue even if model artifacts, experiment stores, or external notification systems are unavailable.

## Product Boundary

AlertPilot is an incident triage platform for SRE, DevOps, and platform engineering teams. The core workflow is operational: alerts arrive, repeated signals collapse into one incident, severity is calculated, ownership is routed, high-severity events are published, responders acknowledge and resolve, and metrics expose system health.

## Runtime Path

1. A monitoring tool sends an alert to `POST /v1/alerts`.
2. Redis applies a sliding-window limit of 100 alerts per minute per client.
3. FastAPI validates the payload with Pydantic and authenticates the bearer token.
4. The triage engine computes a normalized fingerprint from service, environment, and title.
5. Redis checks the fingerprint cache before the database lookup path.
6. Existing open incidents increment their occurrence count; new incidents are created with severity, owner team, service tier, and runbook context.
7. High and critical incidents publish `incident.created` events to Kafka.
8. A Kafka consumer processes the event stream and records notification activity.
9. Audit events record incident creation, acknowledgement, and resolution.
10. Prometheus counters and histograms are updated for operational visibility.

## Offline Path

1. Synthetic production-like alerts are generated with deterministic random seeds.
2. Great Expectations validates schema, enums, non-null columns, and numeric ranges.
3. scikit-learn trains a severity classifier on validated alert records.
4. MLflow records metrics, parameters, and artifacts.
5. DVC locks data, model, metric, and benchmark outputs for reproducibility.
6. Benchmark scripts measure API ingestion throughput, latency percentiles, deduplication behavior, and Redis fingerprint-cache impact.

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
- Redis rate limiting protects the ingestion endpoint from noisy or abusive producers.
- Redis fingerprint caching reduces repeated database fingerprint lookups during alert storms.
- Severity combines service tier, environment, threshold ratio, and keyword signals so the online path does not depend on model availability.
- Kafka decouples high-severity incident creation from downstream notification processing.
- PBKDF2 password hashing and HMAC bearer tokens avoid storing plaintext credentials or relying on hard-coded API keys.
- Admin-only service catalog writes separate operational configuration from ordinary incident response actions.
- Prometheus metrics and structured JSON logs support production-style debugging and monitoring.
- DVC and Great Expectations make the ML/data pipeline reproducible from source.

## Scaling Path

SQLite keeps the project portable for local execution and automated verification, while the module boundaries are shaped for production migration:

- Replace SQLite with Postgres while keeping the repository-style `Database` interface.
- Use Redis Cluster for shared rate-limit counters and fingerprint cache state across API replicas.
- Add strict distributed fingerprint locks for exactly-once incident creation under high concurrency.
- Promote the trained severity classifier behind a feature flag after shadow evaluation.
- Expand Kafka consumers into notification adapters for Slack, PagerDuty, email, or ticketing systems.
- Add OpenTelemetry traces alongside the existing Prometheus metrics.
- Deploy the API behind a managed container platform with external secrets and managed observability.

## Operational Guarantees

| Concern | Approach |
| --- | --- |
| Ingestion availability | Incident creation uses deterministic scoring and does not require an online ML dependency. |
| Duplicate suppression | Open incidents are matched through stable fingerprints derived from normalized alert context. |
| Rate-limit safety | Redis sliding-window counters reject clients that exceed the configured ingestion limit. |
| Event isolation | Kafka event publishing is isolated from the main incident write path. |
| Auditability | Security and incident lifecycle actions are written to audit and event tables. |
| Reproducibility | DVC locks the data generation, validation, training, and benchmark pipeline stages. |
| Observability | Prometheus metrics, structured request logs, health checks, and readiness checks expose runtime state. |
| Deployment portability | Docker, Compose, Kubernetes manifests, and GHCR publishing provide repeatable deployment paths. |

## Measured Verification

- Tests: 58 passed with 93% line coverage.
- Dataset generation and validation: 5,000 alerts.
- Severity classifier: 0.697 accuracy and 0.701 weighted F1.
- API benchmark: 750 requests at 421.65 requests/sec, 3.227 ms p95 latency, 6.005 ms p99 latency.
- Redis fingerprint cache: 99.87% database fingerprint lookup reduction under repeated-alert load.
