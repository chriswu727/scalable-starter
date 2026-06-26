"""Pure domain entity. No framework, no ORM, no I/O — just data + invariants.

Domain objects are what services manipulate. Keeping them free of SQLAlchemy and
Pydantic means business rules can be reasoned about and unit-tested in isolation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Item:
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
