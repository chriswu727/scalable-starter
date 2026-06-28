"""RedisCache adapter tests against a fake, Lua-capable Redis.

The rate limiter's correctness lives in RedisCache.incr (atomic increment +
first-time expiry), so it is exercised here rather than only through the
in-memory test double.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest

from app.cache.aside import get_or_set
from app.cache.redis import RedisCache


@pytest.fixture
async def cache() -> AsyncIterator[RedisCache]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield RedisCache(client)
    await client.aclose()


async def test_incr_with_ttl_counts_and_sets_expiry_once(cache: RedisCache) -> None:
    assert [await cache.incr("rl", ttl_seconds=60) for _ in range(3)] == [1, 2, 3]
    # The window TTL is set on the first increment and not slid forward.
    assert 50 < await cache.client.ttl("rl") <= 60


async def test_incr_without_ttl_has_no_expiry(cache: RedisCache) -> None:
    assert await cache.incr("counter") == 1
    assert await cache.client.ttl("counter") == -1


async def test_get_set_delete_roundtrip(cache: RedisCache) -> None:
    await cache.set("k", "v", ttl_seconds=30)
    assert await cache.get("k") == "v"
    await cache.delete("k")
    assert await cache.get("k") is None


async def test_get_or_set_computes_once_then_caches(cache: RedisCache) -> None:
    calls = 0

    async def factory() -> str:
        nonlocal calls
        calls += 1
        return "value"

    assert await get_or_set(cache, "ca:k1", factory, ttl_seconds=60) == "value"
    assert await get_or_set(cache, "ca:k1", factory, ttl_seconds=60) == "value"
    assert calls == 1  # second call served from cache


async def test_get_or_set_single_flights_a_stampede(cache: RedisCache) -> None:
    calls = 0

    async def factory() -> str:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return "value"

    results = await asyncio.gather(
        *[get_or_set(cache, "ca:hot", factory, ttl_seconds=60) for _ in range(10)]
    )
    assert results == ["value"] * 10
    assert calls == 1  # 10 concurrent misses computed once
