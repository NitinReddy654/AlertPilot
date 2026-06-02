from __future__ import annotations

import hashlib
import time
from collections import defaultdict, deque
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class InMemorySlidingWindowStore:
    def __init__(self):
        self.windows: dict[str, deque[float]] = defaultdict(deque)

    async def count_hit(self, key: str, window_seconds: int, now: float | None = None) -> int:
        now = now if now is not None else time.time()
        window = self.windows[key]
        cutoff = now - window_seconds
        while window and window[0] <= cutoff:
            window.popleft()
        window.append(now)
        return len(window)


class RedisSlidingWindowStore:
    def __init__(self, redis_url: str, key_prefix: str = "alertpilot"):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.client = None
        self.fallback = InMemorySlidingWindowStore()

    async def _get_client(self):
        if self.client is not None:
            return self.client
        try:
            import redis.asyncio as redis

            self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            return self.client
        except Exception:
            self.client = None
            return None

    async def count_hit(self, key: str, window_seconds: int, now: float | None = None) -> int:
        now = now if now is not None else time.time()
        client = await self._get_client()
        if client is None:
            return await self.fallback.count_hit(key, window_seconds, now)
        redis_key = f"{self.key_prefix}:rate:{key}"
        score = int(now * 1000)
        member = f"{score}:{time.perf_counter_ns()}"
        cutoff = score - window_seconds * 1000
        try:
            pipe = client.pipeline()
            pipe.zremrangebyscore(redis_key, 0, cutoff)
            pipe.zadd(redis_key, {member: score})
            pipe.zcard(redis_key)
            pipe.expire(redis_key, window_seconds + 5)
            results = await pipe.execute()
            return int(results[2])
        except Exception:
            self.client = None
            return await self.fallback.count_hit(key, window_seconds, now)


@dataclass
class SlidingWindowRateLimiter:
    store: RedisSlidingWindowStore | InMemorySlidingWindowStore
    limit: int = 100
    window_seconds: int = 60

    async def allow(self, identity: str, now: float | None = None) -> tuple[bool, int]:
        count = await self.store.count_hit(identity, self.window_seconds, now)
        return count <= self.limit, count


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        redis_url: str,
        limit: int = 100,
        window_seconds: int = 60,
        enabled: bool = True,
        store: RedisSlidingWindowStore | InMemorySlidingWindowStore | None = None,
    ):
        super().__init__(app)
        self.enabled = enabled
        selected_store = store or RedisSlidingWindowStore(redis_url)
        self.limiter = SlidingWindowRateLimiter(selected_store, limit=limit, window_seconds=window_seconds)

    async def dispatch(self, request: Request, call_next):
        if not self.enabled or request.method != "POST" or request.url.path != "/v1/alerts":
            return await call_next(request)
        identity = self._identity(request)
        allowed, count = await self.limiter.allow(identity)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Alert ingestion rate limit exceeded",
                    "limit": self.limiter.limit,
                    "window_seconds": self.limiter.window_seconds,
                    "observed_requests": count,
                },
            )
        return await call_next(request)

    def _identity(self, request: Request) -> str:
        token = request.headers.get("authorization") or ""
        if token:
            raw = token.strip()
        elif request.client:
            raw = request.client.host
        else:
            raw = "anonymous"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
