"""Cache abstraction backed by Redis.

Services depend on the :class:`Cache` *protocol*, never on Redis directly, so
tests can substitute :class:`InMemoryCache` and you can swap the backend without
touching business code. The same Redis connection also serves as the broker for
the background-worker queue (see ``app/workers/queue.py``).
"""

from __future__ import annotations

import time
from typing import Protocol, cast, runtime_checkable

import redis.asyncio as aioredis

from app.core.config import settings

# Atomic "increment, and set the TTL only when the key is first created". A Lua
# script runs atomically on the server and — unlike `EXPIRE ... NX` — works on
# Redis 6.x as well as 7+, so the rate limiter behaves correctly on older stores.
_INCR_EXPIRE_LUA = (
    "local c = redis.call('INCR', KEYS[1]) "
    "if c == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end "
    "return c"
)


@runtime_checkable
class Cache(Protocol):
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def incr(self, key: str, *, ttl_seconds: int | None = None) -> int: ...
    async def close(self) -> None: ...


class RedisCache:
    """Production cache backed by Redis."""

    def __init__(self, client: aioredis.Redis) -> None:
        self._client = client

    @property
    def client(self) -> aioredis.Redis:
        return self._client

    async def get(self, key: str) -> str | None:
        return cast("str | None", await self._client.get(key))

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        await self._client.set(key, value, ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def incr(self, key: str, *, ttl_seconds: int | None = None) -> int:
        if ttl_seconds is None:
            return int(await self._client.incr(key))
        # Atomic INCR + first-time EXPIRE, so a crash between the two ops can't
        # orphan a key without a TTL (which would be a permanent throttle).
        return int(await self._client.eval(_INCR_EXPIRE_LUA, 1, key, ttl_seconds))

    async def close(self) -> None:
        await self._client.aclose()


class InMemoryCache:
    """Dependency-free cache for tests and local fallback."""

    def __init__(self) -> None:
        self._store: dict[str, tuple[str, float | None]] = {}

    def _expired(self, key: str) -> bool:
        item = self._store.get(key)
        if item is None:
            return True
        _, expires_at = item
        return expires_at is not None and expires_at < time.monotonic()

    async def get(self, key: str) -> str | None:
        if self._expired(key):
            self._store.pop(key, None)
            return None
        return self._store[key][0]

    async def set(self, key: str, value: str, *, ttl_seconds: int | None = None) -> None:
        expires = time.monotonic() + ttl_seconds if ttl_seconds else None
        self._store[key] = (value, expires)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def incr(self, key: str, *, ttl_seconds: int | None = None) -> int:
        # Set the expiry only when the window is created, mirroring Redis's
        # EXPIRE NX, so repeated increments don't slide the window forward.
        if self._expired(key):
            expires = time.monotonic() + ttl_seconds if ttl_seconds else None
            self._store[key] = ("1", expires)
            return 1
        value, expires = self._store[key]
        current = int(value) + 1
        self._store[key] = (str(current), expires)
        return current

    async def close(self) -> None:
        self._store.clear()


def create_cache() -> Cache:
    """Factory used at startup. Returns a Redis-backed cache.

    Bounded timeouts + periodic health checks so a partitioned Redis fails fast
    instead of wedging the awaiting request. (The worker's *blocking* consumer
    deliberately uses no socket_timeout so BLMOVE isn't cut off — see workers/.)
    """
    client = aioredis.from_url(
        str(settings.redis_url),
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=5,
        health_check_interval=30,
        max_connections=50,
    )
    return RedisCache(client)
