# src/infrastructure/adapters/mariadb/database_context.py

from contextlib import asynccontextmanager
from typing import TypeVar

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

# Import Entities
from src.core.entity import Entity

T = TypeVar("T", bound=Entity)


class DatabaseContext:

    def __init__(self, connection_url: str):
        # It manages connections, timeouts, and the pool size.
        self.engine = create_async_engine(
            connection_url,
            pool_size=30,
            max_overflow=50,
            pool_timeout=30,
            pool_recycle=3600,
        )

        # This is your 'Session Factory' (Connection Factory)
        self.session_factory = async_sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    @asynccontextmanager
    async def get_session(self):
        async with self.session_factory() as session:
            yield session

    async def initialize_database(self) -> None:
        """Create all tables if they don't exist."""
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
