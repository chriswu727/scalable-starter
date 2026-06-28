from __future__ import annotations

from httpx import AsyncClient


async def test_healthz(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_readyz_checks_dependencies(client: AsyncClient) -> None:
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"
    assert body["checks"]["cache"] == "ok"


async def test_readyz_returns_503_when_dependency_down(client: AsyncClient) -> None:
    from app.main import app

    class _BrokenCache:
        async def get(self, *a: object, **k: object) -> str | None:
            raise RuntimeError("cache down")

        async def set(self, *a: object, **k: object) -> None:
            raise RuntimeError("cache down")

        async def delete(self, *a: object, **k: object) -> None:
            raise RuntimeError("cache down")

        async def incr(self, *a: object, **k: object) -> int:
            raise RuntimeError("cache down")

        async def close(self) -> None: ...

    app.state.cache = _BrokenCache()
    resp = await client.get("/readyz")
    assert resp.status_code == 503  # K8s reads the status code, not the body
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["cache"] == "error"
