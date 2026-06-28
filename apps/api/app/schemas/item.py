"""Pydantic DTOs for the example Item resource — the API contract.

Input schemas (``Create``/``Update``) and the output schema (``Read``) are kept
separate so the wire format is decoupled from the database model.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)

    @model_validator(mode="after")
    def _reject_explicit_null_name(self) -> ItemUpdate:
        # ``name`` maps to a NOT NULL column. Omitting it is fine (untouched on
        # PATCH), but an explicit null must be a 422, not a 500 from the database.
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name may not be set to null")
        return self


class ItemRead(ItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
