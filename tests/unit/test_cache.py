import sys
import types

from alertpilot.cache import InMemoryFingerprintCache, RedisCache


def test_in_memory_fingerprint_cache_roundtrip():
    cache = InMemoryFingerprintCache()
    cache.set_fingerprint("abc", "incident-1")
    assert cache.get_fingerprint("abc") == "incident-1"
    cache.set_json("payload", {"ok": "true"})
    assert cache.get_json("payload") == {"ok": "true"}
    assert cache.increment("alerts") == 1
    assert cache.increment("alerts") == 2


def test_redis_cache_falls_back_when_disabled():
    cache = RedisCache("redis://localhost:6379/0", enabled=False)
    cache.set_fingerprint("abc", "incident-1")
    assert cache.get_fingerprint("abc") == "incident-1"
    cache.set_json("payload", {"value": "1"})
    assert cache.get_json("payload") == {"value": "1"}
    assert cache.increment("counter") == 1


def test_redis_cache_uses_client_when_available(monkeypatch):
    class FakeRedisClient:
        def __init__(self):
            self.values = {}
            self.counters = {}

        def get(self, key):
            return self.values.get(key)

        def setex(self, key, ttl, value):
            self.values[key] = value

        def incr(self, key):
            self.counters[key] = self.counters.get(key, 0) + 1
            return self.counters[key]

        def expire(self, key, ttl):
            self.values.setdefault(f"expire:{key}", str(ttl))

    fake_client = FakeRedisClient()
    fake_redis = types.SimpleNamespace(Redis=types.SimpleNamespace(from_url=lambda *args, **kwargs: fake_client))
    monkeypatch.setitem(sys.modules, "redis", fake_redis)

    cache = RedisCache("redis://localhost:6379/0", enabled=True)
    cache.set_fingerprint("fp", "incident-1")
    assert cache.get_fingerprint("fp") == "incident-1"
    cache.set_json("payload", {"severity": "high"})
    assert cache.get_json("payload") == {"severity": "high"}
    assert cache.increment("alerts") == 1


def test_redis_cache_disables_client_on_error(monkeypatch):
    class BrokenClient:
        def get(self, key):
            raise RuntimeError("redis down")

        def setex(self, key, ttl, value):
            raise RuntimeError("redis down")

        def incr(self, key):
            raise RuntimeError("redis down")

    fake_redis = types.SimpleNamespace(Redis=types.SimpleNamespace(from_url=lambda *args, **kwargs: BrokenClient()))
    monkeypatch.setitem(sys.modules, "redis", fake_redis)

    cache = RedisCache("redis://localhost:6379/0", enabled=True)
    assert cache.get_fingerprint("fp") is None
    cache.set_fingerprint("fp", "incident-1")
    assert cache.get_fingerprint("fp") == "incident-1"
    assert cache.increment("alerts") == 1
