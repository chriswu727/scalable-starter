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
    assert resp.json()["code"] == "validation_error"
