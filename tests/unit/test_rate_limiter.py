import asyncio

from alertpilot.middleware.rate_limiter import InMemorySlidingWindowStore, SlidingWindowRateLimiter


def run(coro):
    return asyncio.run(coro)


def test_rate_limiter_allows_requests_under_limit():
    limiter = SlidingWindowRateLimiter(InMemorySlidingWindowStore(), limit=3, window_seconds=60)
    assert run(limiter.allow("client", now=100.0))[0] is True
    assert run(limiter.allow("client", now=101.0))[0] is True
    assert run(limiter.allow("client", now=102.0))[0] is True


def test_rate_limiter_blocks_requests_above_limit():
    limiter = SlidingWindowRateLimiter(InMemorySlidingWindowStore(), limit=2, window_seconds=60)
    assert run(limiter.allow("client", now=100.0))[0] is True
    assert run(limiter.allow("client", now=101.0))[0] is True
    allowed, count = run(limiter.allow("client", now=102.0))
    assert allowed is False
    assert count == 3


def test_rate_limiter_sliding_window_expires_old_hits():
    limiter = SlidingWindowRateLimiter(InMemorySlidingWindowStore(), limit=2, window_seconds=10)
    assert run(limiter.allow("client", now=100.0))[0] is True
    assert run(limiter.allow("client", now=101.0))[0] is True
    assert run(limiter.allow("client", now=111.5))[0] is True


def test_rate_limiter_isolated_by_identity():
    limiter = SlidingWindowRateLimiter(InMemorySlidingWindowStore(), limit=1, window_seconds=60)
    assert run(limiter.allow("client-a", now=100.0))[0] is True
    assert run(limiter.allow("client-a", now=101.0))[0] is False
    assert run(limiter.allow("client-b", now=101.0))[0] is True
