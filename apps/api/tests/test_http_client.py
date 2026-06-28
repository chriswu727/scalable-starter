"""Outbound HTTP client: retries (idempotent only), and the circuit breaker."""

from __future__ import annotations

import httpx
import pytest

from app.core.http_client import CircuitBreaker, CircuitOpenError, HttpClient


def _client(handler: object, **kwargs: object) -> HttpClient:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return HttpClient(httpx.AsyncClient(transport=transport), backoff=0, **kwargs)  # type: ignore[arg-type]


async def test_retries_idempotent_5xx_then_succeeds() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503 if calls < 3 else 200)

    resp = await _client(handler, retries=3).get("http://svc/x")
    assert resp.status_code == 200
    assert calls == 3  # two retries, then success


async def test_does_not_retry_post() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    resp = await _client(handler, retries=3).post("http://svc/x")
    assert resp.status_code == 503
    assert calls == 1  # POST is not idempotent — not retried


async def test_circuit_opens_after_threshold() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    client = _client(handler, retries=0, breaker=CircuitBreaker(threshold=2, cooldown=60))
    await client.get("http://svc/x")  # failure 1
    await client.get("http://svc/x")  # failure 2 -> opens
    with pytest.raises(CircuitOpenError):
        await client.get("http://svc/x")
