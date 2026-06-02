from __future__ import annotations

import json
from typing import Any


class InMemoryFingerprintCache:
    def __init__(self):
        self._store: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    @property
    def enabled(self) -> bool:
        return True

    def get_fingerprint(self, fingerprint: str) -> str | None:
        return self._store.get(fingerprint)

    def set_fingerprint(self, fingerprint: str, incident_id: str, ttl_seconds: int = 60) -> None:
        self._store[fingerprint] = incident_id

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int = 300) -> None:
        self._store[key] = json.dumps(value)

    def get_json(self, key: str) -> dict[str, Any] | None:
        raw = self._store.get(key)
        return json.loads(raw) if raw else None

    def increment(self, key: str) -> int:
        self._counters[key] = self._counters.get(key, 0) + 1
        return self._counters[key]


class RedisCache:
    def __init__(self, redis_url: str, enabled: bool = True, key_prefix: str = "alertpilot"):
        self.key_prefix = key_prefix
        self.client = None
        self.fallback = InMemoryFingerprintCache()
        if enabled:
            try:
                import redis

                self.client = redis.Redis.from_url(redis_url, decode_responses=True)
            except Exception:
                self.client = None

    @property
    def enabled(self) -> bool:
        return self.client is not None

    def _key(self, suffix: str) -> str:
        return f"{self.key_prefix}:{suffix}"

    def _disable_on_error(self) -> None:
        self.client = None

    def get_fingerprint(self, fingerprint: str) -> str | None:
        key = self._key(f"fingerprint:{fingerprint}")
        if self.client is None:
            return self.fallback.get_fingerprint(fingerprint)
        try:
            return self.client.get(key)
        except Exception:
            self._disable_on_error()
            return self.fallback.get_fingerprint(fingerprint)

    def set_fingerprint(self, fingerprint: str, incident_id: str, ttl_seconds: int = 60) -> None:
        key = self._key(f"fingerprint:{fingerprint}")
        if self.client is None:
            self.fallback.set_fingerprint(fingerprint, incident_id, ttl_seconds)
            return
        try:
            self.client.setex(key, ttl_seconds, incident_id)
        except Exception:
            self._disable_on_error()
            self.fallback.set_fingerprint(fingerprint, incident_id, ttl_seconds)

    def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int = 300) -> None:
        namespaced = self._key(key)
        if self.client is None:
            self.fallback.set_json(key, value, ttl_seconds)
            return
        try:
            self.client.setex(namespaced, ttl_seconds, json.dumps(value))
        except Exception:
            self._disable_on_error()
            self.fallback.set_json(key, value, ttl_seconds)

    def get_json(self, key: str) -> dict[str, Any] | None:
        namespaced = self._key(key)
        if self.client is None:
            return self.fallback.get_json(key)
        try:
            raw = self.client.get(namespaced)
            return json.loads(raw) if raw else None
        except Exception:
            self._disable_on_error()
            return self.fallback.get_json(key)

    def increment(self, key: str) -> int:
        namespaced = self._key(key)
        if self.client is None:
            return self.fallback.increment(key)
        try:
            value = self.client.incr(namespaced)
            self.client.expire(namespaced, 3600)
            return int(value)
        except Exception:
            self._disable_on_error()
            return self.fallback.increment(key)
