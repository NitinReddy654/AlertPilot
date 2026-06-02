import asyncio
import sys
import types

from alertpilot.middleware.rate_limiter import RedisSlidingWindowStore


def run(coro):
    return asyncio.run(coro)


def test_redis_sliding_window_store_falls_back_when_ping_fails(monkeypatch):
    class BrokenRedis:
        async def ping(self):
            raise RuntimeError("down")

    fake_redis = types.SimpleNamespace(Redis=types.SimpleNamespace(from_url=lambda *args, **kwargs: BrokenRedis()))
    monkeypatch.setitem(sys.modules, "redis.asyncio", fake_redis)
    store = RedisSlidingWindowStore("redis://localhost:6379/0")
    assert run(store.count_hit("client", 60, now=100.0)) == 1


def test_redis_sliding_window_store_uses_pipeline(monkeypatch):
    class FakePipeline:
        def zremrangebyscore(self, *args):
            return self

        def zadd(self, *args):
            return self

        def zcard(self, *args):
            return self

        def expire(self, *args):
            return self

        async def execute(self):
            return [0, 1, 2, True]

    class FakeRedis:
        async def ping(self):
            return True

        def pipeline(self):
            return FakePipeline()

    store = RedisSlidingWindowStore("redis://localhost:6379/0")

    async def fake_get_client():
        return FakeRedis()

    monkeypatch.setattr(store, "_get_client", fake_get_client)
    assert run(store.count_hit("client", 60, now=100.0)) == 2
