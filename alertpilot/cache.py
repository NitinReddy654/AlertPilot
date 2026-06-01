from __future__ import annotations

import json
from typing import Any


class OptionalRedisCache:
    def __init__(self, enabled: bool, redis_url: str):
        self.client = None
        if enabled:
            try:
                import redis

                self.client = redis.Redis.from_url(redis_url, decode_responses=True)
                self.client.ping()
            except Exception:
                self.client = None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int = 300) -> None:
        if self.client is None:
            return
        self.client.setex(key, ttl_seconds, json.dumps(value))

    def get_json(self, key: str) -> dict[str, Any] | None:
        if self.client is None:
            return None
        raw = self.client.get(key)
        return json.loads(raw) if raw else None

    def increment(self, key: str) -> None:
        if self.client is not None:
            self.client.incr(key)
