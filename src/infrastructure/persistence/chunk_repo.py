import threading
from typing import Any, List

from lancedb.table import LanceTable
from src.core.config import Settings
from src.core.text_chunk import TextChunk
from src.infrastructure.adapters.vectors.vector_database_context import (
    VectorDatabaseContext,
)
from src.infrastructure.persistence.vector_base_repository import VectorRepository


class ChunkRepository(VectorRepository):
    def __init__(self, table: "LanceTable"):
        self._table = table
        self._write_lock = threading.Lock()

    @classmethod
    async def create(
        cls,
        settings: Settings,
        vector_ctx: VectorDatabaseContext,
    ) -> "ChunkRepository":
        """Factory method to initialize the repository with the correct table."""
        table = await vector_ctx.get_table(settings.vector_index_name)
        return cls(table)

    async def save_chunks(self, chunks: List[TextChunk]) -> None:
        """
        Saves chunks directly to LanceDB.
        Expects chunks to already have their 'vector' field populated.
        """
        if not chunks:
            return

        data = []
        for chunk in chunks:
            if chunk.vector is None:
                raise ValueError(f"Chunk {chunk.id} is missing its embedding vector.")

            # Convert Pydantic model to dict for LanceDB
            data.append(chunk.model_dump())

        with self._write_lock:
            await self._table.add(data)

    async def search_chunks(
        self, query_vector: List[float], book_id: str, path_id: str, top_k: int = 5
    ) -> List[dict[str, Any]]:
        """
        Search chunks using a pre-calculated vector.
        The caller (Service/Operation) is now responsible for embedding the query.
        """
        return await (
            self._table.search(query_vector)
            .where(
                f"book_id = '{book_id}' AND path_id LIKE '{path_id}%'", prefilter=True
            )
            .limit(top_k)
            .to_list()
        )

    async def delete_book(self, book_id: str) -> None:
        await self._table.delete(f"book_id = '{book_id}'")

    async def get_chunks_by_book(self, book_id: str) -> List[TextChunk]:
        """Retrieve all chunks for a book using LanceDB's native scanner."""
        results = await self._table.query().where(f"book_id = '{book_id}'").to_list()
        return [TextChunk(**r) for r in results]

    async def get_chunks_by_section(self, section_id: str) -> List[TextChunk]:
        """Retrieve all chunks for a specific section."""
        results = (
            await self._table.query().where(f"section_id = '{section_id}'").to_list()
        )
        return [TextChunk(**r) for r in results]
