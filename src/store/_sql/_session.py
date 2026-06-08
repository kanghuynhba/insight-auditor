# src/store/_sql/_session.py

from contextlib import asynccontextmanager
from typing import TypeVar

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domain.entity import Entity
import src.domain  # noqa: F401 - register SQLModel table classes before create_all

T = TypeVar("T", bound=Entity)


class DatabaseContext:

    def __init__(self, connection_url: str):
        self.connection_url = connection_url
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
        await self._ensure_database_exists()
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

    async def _ensure_database_exists(self) -> None:
        url = make_url(self.connection_url)
        database = url.database
        if not database:
            return

        try:
            async with self.engine.begin():
                return
        except OperationalError as exc:
            if not self._is_unknown_database_error(exc):
                raise

        server_url = url.set(database=None)
        server_engine = create_async_engine(str(server_url))
        escaped_database = database.replace("`", "``")
        try:
            async with server_engine.begin() as conn:
                await conn.execute(
                    text(
                        f"CREATE DATABASE IF NOT EXISTS `{escaped_database}` "
                        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                    )
                )
        finally:
            await server_engine.dispose()

    @staticmethod
    def _is_unknown_database_error(exc: OperationalError) -> bool:
        orig = getattr(exc, "orig", None)
        args = getattr(orig, "args", ())
        return bool(args and args[0] == 1049)
