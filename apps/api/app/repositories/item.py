"""Concrete repository for the example Item model."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.item import ItemModel
from app.repositories.base import BaseRepository


class ItemRepository(BaseRepository[ItemModel]):
    model = ItemModel

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_name(self, name: str) -> ItemModel | None:
        stmt = select(ItemModel).where(ItemModel.name == name)
        return await self.session.scalar(stmt)
