"""Cache-aside (read-through) helper with single-flight stampede protection."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.cache.redis import Cache

# One lock per key: a stampede of concurrent misses computes the value once per
# process, not once per request. (Bounded set of cacheable keys assumed; for a
# hot key shared across pods, add a distributed lock e.g. Redis SET NX.)
_locks: dict[str, asyncio.Lock] = {}


async def get_or_set(
    cache: Cache,
    key: str,
    factory: Callable[[], Awaitable[str]],
    *,
    ttl_seconds: int,
) -> str:
    """Return ``cache[key]``, or compute it via ``factory()``, store, and return."""
    cached = await cache.get(key)
    if cached is not None:
        return cached
    lock = _locks.setdefault(key, asyncio.Lock())
    async with lock:
        cached = await cache.get(key)  # double-check: another waiter may have filled it
        if cached is not None:
            return cached
        value = await factory()
        await cache.set(key, value, ttl_seconds=ttl_seconds)
        return value
