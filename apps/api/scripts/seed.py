#!/usr/bin/env python3
"""Insert a few example rows, idempotently. Run against a live database:

    make seed          # or, from apps/api:  python scripts/seed.py

Safe to re-run — existing names are skipped. Edit SEED for your own data.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.db.models.item import ItemModel

SEED: list[tuple[str, str | None]] = [
    ("alpha", "the first seeded item"),
    ("beta", "the second seeded item"),
    ("gamma", None),
]


async def seed() -> None:
    engine = create_async_engine(settings.sqlalchemy_dsn)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            inserted = 0
            for name, description in SEED:
                if await session.scalar(select(ItemModel).where(ItemModel.name == name)):
                    continue
                session.add(ItemModel(name=name, description=description))
                inserted += 1
            await session.commit()
            print(f"seeded {inserted} new item(s) ({len(SEED) - inserted} already present)")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
