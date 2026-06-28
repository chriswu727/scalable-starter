"""Item use-cases. Your business rules live in the service layer.

The service depends on the repository interface and raises domain exceptions; it
knows nothing about HTTP. This is the layer you will spend most of your time in.
"""

from __future__ import annotations

import uuid

from app.db.models.item import ItemModel
from app.exceptions import ConflictError, NotFoundError
from app.repositories.item import ItemRepository
from app.schemas.item import ItemCreate, ItemUpdate


class ItemService:
    def __init__(self, repository: ItemRepository) -> None:
        self.repository = repository

    async def get(self, item_id: uuid.UUID) -> ItemModel:
        item = await self.repository.get(item_id)
        if item is None:
            raise NotFoundError(f"Item {item_id} does not exist")
        return item

    async def list(self, *, limit: int, offset: int) -> tuple[list[ItemModel], int]:
        items = await self.repository.list(limit=limit, offset=offset)
        total = await self.repository.count()
        return items, total

    async def create(self, payload: ItemCreate) -> ItemModel:
        # Example business rule: names must be unique.
        if await self.repository.get_by_name(payload.name) is not None:
            raise ConflictError(f"An item named {payload.name!r} already exists")
        return await self.repository.create(name=payload.name, description=payload.description)

    async def update(self, item_id: uuid.UUID, payload: ItemUpdate) -> ItemModel:
        item = await self.get(item_id)
        # exclude_unset: only fields the client actually sent are updated, so an
        # omitted field is left untouched while an explicit null clears it.
        return await self.repository.update(item, **payload.model_dump(exclude_unset=True))

    async def delete(self, item_id: uuid.UUID) -> None:
        deleted = await self.repository.delete(item_id)
        if deleted == 0:
            raise NotFoundError(f"Item {item_id} does not exist")
