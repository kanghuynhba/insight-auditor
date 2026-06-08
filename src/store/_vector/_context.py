# src/infrastructure/adapters/vectors/vector_database_context.py
import asyncio

import lancedb
from src.domain.config import Settings
from src.domain.text_chunk import TextChunk


class VectorDatabaseContext:
    def __init__(self, settings: Settings):
        self.db_uri = str(settings.lance_db_path)
        self._db = None
        self._tables = {}  # Cache table handles
        self._lock = asyncio.Lock()  # Prevent race conditions on connect

    async def connect(self):
        async with self._lock:
            if self._db is None:
                # Use the async connection
                self._db = await lancedb.connect_async(self.db_uri)
            return self._db

    async def get_table(self, table_name: str):
        # 1. Ensure we are connected
        db = await self.connect()

        # 2. Check cache first to avoid re-opening file descriptors
        if table_name not in self._tables:
            async with self._lock:
                if table_name not in self._tables:
                    self._tables[table_name] = await db.open_table(table_name)

        return self._tables[table_name]
