from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base
from app.db import models as _models  # noqa: F401

engine: AsyncEngine | None = None
session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str) -> None:
    global engine, session_factory

    if engine is not None:
        return

    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def close_engine() -> None:
    global engine, session_factory
    if engine is not None:
        await engine.dispose()
    engine = None
    session_factory = None


async def create_schema() -> None:
    if engine is None:
        raise RuntimeError("Database engine not initialized.")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def ping_db() -> None:
    if session_factory is None:
        raise RuntimeError("Database session factory not initialized.")
    async with session_factory() as session:
        await session.execute(text("SELECT 1"))


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if session_factory is None:
        raise RuntimeError("Database session factory not initialized.")
    async with session_factory() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncGenerator[AsyncSession, None]:
    if session_factory is None:
        raise RuntimeError("Database session factory not initialized.")
    async with session_factory() as session:
        yield session
