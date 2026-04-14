# src/infrastructure/storage/mariadb_storage.py

import json
import logging
import re
from collections.abc import Iterator
from datetime import datetime
from io import BytesIO
from typing import Any
from typing import Iterator as TypingIterator

import pandas as pd
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from src.infrastructure.storage.storage import Storage

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class MariaDBStorage(Storage):
    def __init__(self, connection_url: str, table_name: str = "storage"):
        # Expects: "mysql+aiomysql://user:pass@host/dbname"
        self._engine = create_async_engine(connection_url)
        self._table_name = table_name

    async def _ensure_table(self) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {self._table_name} (
                    id VARCHAR(255) PRIMARY KEY,
                    body LONGTEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """))

    async def set(self, key: str, value: Any, encoding: str | None = None) -> None:
        """
        Store an atomicfact or list of facts into mariadb.
        'value' is typically a pydantic model or a list of models.
        """
        await self._ensure_table()

        if isinstance(value, list):
            serialized_value = json.dumps(
                [item.model_dump() for item in value], cls=DateTimeEncoder
            )
        elif hasattr(value, "model_dump"):
            serialized_value = json.dumps(value.model_dump(), cls=DateTimeEncoder)
        else:
            serialized_value = json.dumps(value, cls=DateTimeEncoder)

        async with self._engine.begin() as conn:
            await conn.execute(
                text(f"""
                    INSERT INTO {self._table_name} (id, body)
                    VALUES (:id, :body)
                    ON DUPLICATE KEY UPDATE body = :body
                """),
                {"id": key, "body": serialized_value},
            )

    async def get(
        self, key: str, as_bytes: bool | None = None, encoding: str | None = None
    ) -> Any:
        """
        Retrieves a single item or a collection of facts from MariaDB.
        """
        async with self._engine.connect() as conn:
            if as_bytes:
                prefix = key.split(".")[0]
                result = await conn.execute(
                    text(f"SELECT body FROM {self._table_name} WHERE id LIKE :prefix"),
                    {"prefix": f"{prefix}:%"},
                )
                rows = result.fetchall()
                if not rows:
                    return None
                return [json.loads(r[0]) for r in rows]

            result = await conn.execute(
                text(f"SELECT body FROM {self._table_name} WHERE id = :id"), {"id": key}
            )
            row = result.fetchone()
            if not row:
                return None
            return json.loads(row[0])

    async def has(self, key: str) -> bool:
        """Return True if the given key exists in the storage."""
        async with self._engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT 1 FROM {self._table_name} WHERE id = :id LIMIT 1"),
                {"id": key},
            )
            return result.fetchone() is not None

    async def delete(self, key: str) -> None:
        """Delete the given key from the storage."""
        async with self._engine.begin() as conn:
            await conn.execute(
                text(f"DELETE FROM {self._table_name} WHERE id = :id"), {"id": key}
            )

    async def clear(self) -> None:
        """Clear the storage."""
        async with self._engine.begin() as conn:
            await conn.execute(text(f"TRUNCATE TABLE {self._table_name}"))

    def find(self, file_pattern: re.Pattern[str]) -> Iterator[str]:
        """Find files in the storage using a file pattern."""
        # This method is synchronous but needs to be implemented
        # For async pattern matching, you might need a different approach
        raise NotImplementedError("find method not implemented for MariaDBStorage")

    def child(self, name: str | None) -> "Storage":
        """Create a child storage instance."""
        # This returns a new storage instance with a prefix
        if name:
            return MariaDBStorage(
                self._engine.url.render_as_string(hide_password=False),
                table_name=f"{self._table_name}_{name}",
            )
        return self

    def keys(self) -> list[str]:
        """List all keys in the storage."""
        # This is synchronous - you might want to make it async
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        async def _get_keys():
            async with self._engine.connect() as conn:
                result = await conn.execute(text(f"SELECT id FROM {self._table_name}"))
                return [row[0] for row in result.fetchall()]

        return loop.run_until_complete(_get_keys())
