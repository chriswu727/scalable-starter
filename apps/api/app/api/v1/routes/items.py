"""Example resource wired end-to-end across every layer.

This exists solely to demonstrate the conventions — routing, validation, service
calls, pagination, status codes, and error mapping. Copy it as a template for
real resources, then delete it.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from app.api.v1.deps import ItemServiceDep, ReadItemServiceDep, rate_limit
from app.schemas.common import Page
from app.schemas.item import ItemCreate, ItemRead, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=Page[ItemRead], summary="List items")
async def list_items(
    service: ReadItemServiceDep,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[ItemRead]:
    items, total = await service.list(limit=limit, offset=offset)
    return Page[ItemRead](
        items=[ItemRead.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=ItemRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an item",
    dependencies=[rate_limit(limit=30, window_seconds=60)],
)
async def create_item(payload: ItemCreate, service: ItemServiceDep) -> ItemRead:
    item = await service.create(payload)
    return ItemRead.model_validate(item)


@router.get("/{item_id}", response_model=ItemRead, summary="Get an item")
async def get_item(item_id: uuid.UUID, service: ReadItemServiceDep) -> ItemRead:
    item = await service.get(item_id)
    return ItemRead.model_validate(item)


@router.patch("/{item_id}", response_model=ItemRead, summary="Update an item")
async def update_item(item_id: uuid.UUID, payload: ItemUpdate, service: ItemServiceDep) -> ItemRead:
    item = await service.update(item_id, payload)
    return ItemRead.model_validate(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an item")
async def delete_item(item_id: uuid.UUID, service: ItemServiceDep) -> None:
    await service.delete(item_id)
