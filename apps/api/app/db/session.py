"""Async engine + session lifecycle.

One write engine (the primary) plus an optional read engine pointed at a
replica via ``DATABASE_READ_URL``. ``get_session`` yields a read/write session
committed at the request boundary; ``get_read_session`` yields a read-only
session that uses the replica when configured and otherwise falls back to the
primary — so read endpoints offload to replicas without touching service code.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None
_read_engine: AsyncEngine | None = None
_read_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine() -> None:
    """Create the global engine(s) + session factories. Idempotent."""
    global _engine, _sessionmaker, _read_engine, _read_sessionmaker
    if _engine is not None:
        return
    _engine = create_async_engine(
        settings.sqlalchemy_dsn,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # detect dropped connections before using them
    )
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False, autoflush=False)

    if settings.database_read_url is not None:
        _read_engine = create_async_engine(
            settings.sqlalchemy_read_dsn,
            echo=settings.db_echo,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
        )
        _read_sessionmaker = async_sessionmaker(
            _read_engine, expire_on_commit=False, autoflush=False
        )


async def dispose_engine() -> None:
    global _engine, _sessionmaker, _read_engine, _read_sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
    if _read_engine is not None:
        await _read_engine.dispose()
        _read_engine = None
        _read_sessionmaker = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: a read/write session scoped to one request."""
    if _sessionmaker is None:
        init_engine()
    assert _sessionmaker is not None
    async with _sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_read_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: a read-only session, served by the replica if set."""
    if _sessionmaker is None:
        init_engine()
    maker = _read_sessionmaker or _sessionmaker
    assert maker is not None
    async with maker() as session:
        yield session  # read-only: no commit
