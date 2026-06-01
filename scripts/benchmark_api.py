from __future__ import annotations

import json
import logging
import sys
import statistics
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from alertpilot.config import Settings
from alertpilot.main import create_app


logging.getLogger("alertpilot").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Settings(database_path=str(Path(tmp) / "bench.db"), token_secret="bench-secret", log_level="WARNING"))
        client = TestClient(app)
        login = client.post("/v1/auth/login", json={"email": "admin@alertpilot.local", "password": "changeme"})
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        latencies = []
        total = 750
        started = time.perf_counter()
        for i in range(total):
            payload = {
                "source": "prometheus",
                "title": "checkout-api p95 latency above SLO",
                "description": "Synthetic benchmark alert",
                "service": "checkout-api",
                "environment": "prod",
                "metric_name": "latency_p95",
                "metric_value": 1.2 + (i % 7) * 0.1,
                "threshold": 0.75,
                "labels": {"pod": f"checkout-{i % 11}"},
            }
            t0 = time.perf_counter()
            response = client.post("/v1/alerts", json=payload, headers=headers)
            response.raise_for_status()
            latencies.append((time.perf_counter() - t0) * 1000)
        elapsed = time.perf_counter() - started
        result = {
            "requests": total,
            "throughput_rps": round(total / elapsed, 2),
            "latency_ms_avg": round(statistics.mean(latencies), 3),
            "latency_ms_p50": round(percentile(latencies, 50), 3),
            "latency_ms_p95": round(percentile(latencies, 95), 3),
            "latency_ms_p99": round(percentile(latencies, 99), 3),
            "deduplicated_occurrences": client.get("/v1/summary", headers=headers).json()["total_occurrences"],
        }
    out = Path("artifacts/benchmarks/api_benchmark.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    Path("artifacts/benchmarks/api_benchmark.md").write_text(
        "# API Benchmark\n\n"
        f"- Requests: {result['requests']}\n"
        f"- Throughput: {result['throughput_rps']} req/s\n"
        f"- Average latency: {result['latency_ms_avg']} ms\n"
        f"- p95 latency: {result['latency_ms_p95']} ms\n"
        f"- p99 latency: {result['latency_ms_p99']} ms\n"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
