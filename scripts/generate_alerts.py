from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SERVICES = [
    ("checkout-api", "payments-platform", 0),
    ("identity-api", "security-platform", 0),
    ("search-api", "discovery", 1),
    ("email-worker", "growth-platform", 2),
]
TITLES = [
    ("p95 latency above SLO", "latency"),
    ("error rate above threshold", "error_rate"),
    ("service unavailable", "availability"),
    ("worker queue backlog high", "queue_depth"),
    ("CPU saturation detected", "cpu"),
]


def label_severity(service_tier: int, environment: str, metric_value: float, threshold: float, title: str) -> str:
    ratio = metric_value / threshold
    if environment == "prod" and ("unavailable" in title or ratio >= 2.4 or service_tier == 0 and ratio >= 1.7):
        return "critical"
    if environment == "prod" and ("error" in title or "latency" in title or ratio >= 1.35):
        return "high"
    if environment == "prod" or ratio >= 1.1:
        return "medium"
    return "low"


def main() -> None:
    rng = np.random.default_rng(42)
    rows = []
    for i in range(5000):
        service, owner_team, tier = SERVICES[int(rng.integers(0, len(SERVICES)))]
        title_suffix, metric_name = TITLES[int(rng.integers(0, len(TITLES)))]
        environment = "prod" if rng.random() < 0.72 else "staging"
        threshold = float(rng.choice([0.75, 1.0, 5.0, 100.0]))
        multiplier = float(rng.lognormal(mean=0.18 + (0.16 if tier == 0 else 0), sigma=0.48))
        metric_value = round(threshold * multiplier, 4)
        title = f"{service} {title_suffix}"
        severity = label_severity(tier, environment, metric_value, threshold, title)
        rows.append(
            {
                "alert_id": f"alert-{i:05d}",
                "source": rng.choice(["prometheus", "cloudwatch", "datadog"]),
                "service": service,
                "owner_team": owner_team,
                "tier": tier,
                "environment": environment,
                "title": title,
                "metric_name": metric_name,
                "metric_value": metric_value,
                "threshold": threshold,
                "severity": severity,
            }
        )
    out = Path("data/generated/alerts.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
