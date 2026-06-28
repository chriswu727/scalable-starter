"""Service-layer unit tests against a fake repository — no DB, no HTTP.

This is the payoff of the layered design: business rules tested in isolation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.db.models.item import ItemModel
from app.exceptions import ConflictError, NotFoundError
from app.schemas.item import ItemCreate, ItemUpdate
from app.services.item import ItemService


class FakeItemRepository:
    """In-memory stand-in for ItemRepository (same method surface the service uses)."""

    def __init__(self) -> None:
        self.items: dict[uuid.UUID, ItemModel] = {}

    async def get(self, id_: uuid.UUID) -> ItemModel | None:
        return self.items.get(id_)

    async def get_by_name(self, name: str) -> ItemModel | None:
        return next((i for i in self.items.values() if i.name == name), None)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[ItemModel]:
        return list(self.items.values())[offset : offset + limit]

    async def count(self) -> int:
        return len(self.items)

    async def create(self, *, name: str, description: str | None) -> ItemModel:
        now = datetime.now(UTC)
        item = ItemModel(
            id=uuid.uuid4(), name=name, description=description, created_at=now, updated_at=now
        )
        self.items[item.id] = item
        return item

    async def update(self, instance: ItemModel, **values: object) -> ItemModel:
        for key, value in values.items():
            setattr(instance, key, value)
        return instance

    async def delete(self, id_: uuid.UUID) -> int:
        return 1 if self.items.pop(id_, None) is not None else 0


def _service() -> ItemService:
    return ItemService(FakeItemRepository())  # type: ignore[arg-type]


async def test_create_then_get_roundtrips() -> None:
    svc = _service()
    created = await svc.create(ItemCreate(name="alpha", description="d"))
    fetched = await svc.get(created.id)
    assert fetched.name == "alpha"


async def test_create_duplicate_name_raises_conflict() -> None:
    svc = _service()
    await svc.create(ItemCreate(name="dup"))
    with pytest.raises(ConflictError):
        await svc.create(ItemCreate(name="dup"))


async def test_get_missing_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        await _service().get(uuid.uuid4())


async def test_update_missing_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        await _service().update(uuid.uuid4(), ItemUpdate(name="x"))


async def test_delete_missing_raises_not_found() -> None:
    with pytest.raises(NotFoundError):
        await _service().delete(uuid.uuid4())
