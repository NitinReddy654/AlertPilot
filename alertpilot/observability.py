from __future__ import annotations

import json
import logging
import time

from fastapi import Request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "alertpilot_http_requests_total",
    "Total HTTP requests.",
    ["path", "method", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "alertpilot_http_request_latency_seconds",
    "HTTP request latency in seconds.",
    ["path", "method"],
)
INCIDENTS_CREATED = Counter(
    "alertpilot_incidents_created_total",
    "Incidents created from incoming alerts.",
)
ALERTS_DEDUPLICATED = Counter(
    "alertpilot_alerts_deduplicated_total",
    "Alerts deduplicated into existing incidents.",
)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(message)s",
        force=True,
    )


class JsonRequestLogger(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        REQUEST_COUNT.labels(request.url.path, request.method, str(response.status_code)).inc()
        REQUEST_LATENCY.labels(request.url.path, request.method).observe(elapsed_ms / 1000)
        logging.info(
            json.dumps(
                {
                    "event": "http_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": round(elapsed_ms, 3),
                }
            )
        )
        return response


def prometheus_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
