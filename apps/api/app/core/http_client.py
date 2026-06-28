"""A sanctioned outbound HTTP client.

A fork's first call to an external API shouldn't be unbounded-timeout,
no-retry, no-breaker. This wraps a pooled ``httpx.AsyncClient`` with bounded
timeouts, retry-with-backoff for *idempotent* methods, and a small circuit
breaker. Create it once in lifespan (``app.state.http``) and share it.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.logging import get_logger

log = get_logger(__name__)

# Only methods safe to retry (a retried POST could double-charge).
_IDEMPOTENT = {"GET", "HEAD", "OPTIONS", "PUT", "DELETE"}


class CircuitOpenError(RuntimeError):
    """Raised when the breaker is open, so callers fail fast instead of piling on."""


class CircuitBreaker:
    """Opens after ``threshold`` consecutive failures, stays open for ``cooldown``."""

    def __init__(self, *, threshold: int = 5, cooldown: float = 30.0) -> None:
        self._threshold = threshold
        self._cooldown = cooldown
        self._failures = 0
        self._open_until = 0.0

    def allow(self, now: float) -> bool:
        return now >= self._open_until

    def record_success(self) -> None:
        self._failures = 0
        self._open_until = 0.0

    def record_failure(self, now: float) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._open_until = now + self._cooldown


class HttpClient:
    """Pooled httpx client with retries (idempotent methods only) + a breaker."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        retries: int = 2,
        backoff: float = 0.2,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self._client = client
        self._retries = retries
        self._backoff = backoff
        self._breaker = breaker or CircuitBreaker()

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        loop = asyncio.get_running_loop()
        if not self._breaker.allow(loop.time()):
            raise CircuitOpenError("outbound circuit is open")

        idempotent = method.upper() in _IDEMPOTENT
        attempt = 0
        while True:
            try:
                response = await self._client.request(method, url, **kwargs)
            except httpx.TransportError:
                self._breaker.record_failure(loop.time())
                if idempotent and attempt < self._retries:
                    await asyncio.sleep(self._backoff * 2**attempt)
                    attempt += 1
                    continue
                raise

            if response.status_code >= 500:
                self._breaker.record_failure(loop.time())
                if idempotent and attempt < self._retries:
                    await asyncio.sleep(self._backoff * 2**attempt)
                    attempt += 1
                    continue
            else:
                self._breaker.record_success()
            return response

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self.request("POST", url, **kwargs)

    async def aclose(self) -> None:
        await self._client.aclose()


def create_http_client() -> HttpClient:
    """Factory used at startup. Bounded timeouts + a bounded connection pool."""
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(5.0, connect=5.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
    )
    return HttpClient(client)
