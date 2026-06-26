"""Import all models here so Alembic's autogenerate sees them via ``Base.metadata``."""

from app.db.models.item import ItemModel

__all__ = ["ItemModel"]
