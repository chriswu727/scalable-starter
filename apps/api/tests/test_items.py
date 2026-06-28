from __future__ import annotations

from httpx import AsyncClient


async def test_item_crud_lifecycle(client: AsyncClient) -> None:
    # Create
    resp = await client.post("/api/v1/items", json={"name": "alpha", "description": "first"})
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "alpha"
    item_id = created["id"]

    # Get
    resp = await client.get(f"/api/v1/items/{item_id}")
    assert resp.status_code == 200

    # List (paginated envelope)
    resp = await client.get("/api/v1/items")
    assert resp.status_code == 200
    page = resp.json()
    assert page["total"] == 1
    assert page["limit"] == 50

    # Update
    resp = await client.patch(f"/api/v1/items/{item_id}", json={"description": "updated"})
    assert resp.status_code == 200
    assert resp.json()["description"] == "updated"

    # Delete
    resp = await client.delete(f"/api/v1/items/{item_id}")
    assert resp.status_code == 204

    # Now gone -> 404 problem+json
    resp = await client.get(f"/api/v1/items/{item_id}")
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_found"


async def test_duplicate_name_conflicts(client: AsyncClient) -> None:
    await client.post("/api/v1/items", json={"name": "dup"})
    resp = await client.post("/api/v1/items", json={"name": "dup"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "conflict"


async def test_validation_error_is_problem_json(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/items", json={"name": ""})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "validation_error"
    assert body["errors"]  # field-level detail present and serialized


async def test_patch_clears_nullable_field(client: AsyncClient) -> None:
    created = await client.post("/api/v1/items", json={"name": "withdesc", "description": "here"})
    item_id = created.json()["id"]

    resp = await client.patch(f"/api/v1/items/{item_id}", json={"description": None})
    assert resp.status_code == 200
    assert resp.json()["description"] is None  # explicit null clears the field


async def test_patch_null_name_is_rejected(client: AsyncClient) -> None:
    created = await client.post("/api/v1/items", json={"name": "hasname"})
    item_id = created.json()["id"]

    # name maps to a NOT NULL column: explicit null is a 422, never a 500.
    resp = await client.patch(f"/api/v1/items/{item_id}", json={"name": None})
    assert resp.status_code == 422
    assert resp.json()["code"] == "validation_error"


async def test_patch_leaves_omitted_fields_untouched(client: AsyncClient) -> None:
    created = await client.post("/api/v1/items", json={"name": "keepname", "description": "orig"})
    item_id = created.json()["id"]

    resp = await client.patch(f"/api/v1/items/{item_id}", json={"description": "changed"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "keepname"  # omitted field is not touched
    assert body["description"] == "changed"


async def test_rate_limit_returns_429_with_retry_after(client: AsyncClient) -> None:
    # create_item allows 30 requests / 60s; the 31st must be throttled.
    last = None
    for i in range(31):
        last = await client.post("/api/v1/items", json={"name": f"rl-{i}"})
    assert last is not None
    assert last.status_code == 429
    assert last.json()["code"] == "rate_limited"
    assert last.headers["retry-after"] == "60"
