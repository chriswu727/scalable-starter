"""RedisCache adapter tests against a fake, Lua-capable Redis.

The rate limiter's correctness lives in RedisCache.incr (atomic increment +
first-time expiry), so it is exercised here rather than only through the
in-memory test double.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest

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
