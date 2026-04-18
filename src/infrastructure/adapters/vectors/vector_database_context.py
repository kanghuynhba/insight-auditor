# src/infrastructure/adapters/vectors/vector_database_context.py

import lancedb
from src.core.config import Settings
from src.core.text_chunk import TextChunk


class VectorDatabaseContext:
    def __init__(self, settings: Settings):
        self.db_uri = str(settings.lance_db_path)
        self._db = None

    async def connect(self):
        if self._db is None:
            self._db = await lancedb.connect_async(str(self.db_uri))
        return self._db

    async def initialize_vector_database(self):
        db = await self.connect()

        existing_tables = await db.table_names()
        if "text_chunk" not in existing_tables:
            await self._db.create_table("text_chunk", schema=TextChunk)

    async def get_table(self, table_name: str):
        db = await self.connect()
        return await db.open_table(table_name)
