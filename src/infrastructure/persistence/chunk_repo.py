# src/infrastructure/persistence/chunk_repo.py
import threading
import time
from typing import Any

import lancedb
from lancedb.table import LanceTable
from src.core.config import Settings
from src.core.text_chunk import TextChunk
from src.infrastructure.adapters.mariadb.vector_database_context import (
    VectorDatabaseContext,
)
from src.infrastructure.llm.embedding.embedding import LLMEmbedding
from src.infrastructure.persistence.vector_base_repository import VectorRepository


class ChunkRepository(VectorRepository):
    def __init__(self, embedder: LLMEmbedding, table: "LanceTable"):
        self._embedder = embedder
        self._table = table
        self._write_lock = threading.Lock()

    @classmethod
    async def create(
        cls,
        settings: Settings,
        vector_ctx: VectorDatabaseContext,
        embedder: "LLMEmbedding",
    ) -> ChunkRepository:
        table = await vector_ctx.get_table(settings.vector_index_name)
        return cls(embedder, table)

    def save_chunks(self, chunks: list[TextChunk]) -> None:
        if not chunks:
            return

        texts = [chunk.text for chunk in chunks]
        response = self._embedder.embed(input=texts)
        vectors = response.embeddings

        data = []
        for chunk, vector in zip(chunks, vectors):
            row = chunk.model_dump()
            row["vector"] = vector
            data.append(row)

        with self._write_lock:
            self._table.add(data)

    def search_chunks(
        self, query: str, book_id: str, path_id: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        query_vector = self._embedder.embed(input=[query]).first_embedding
        return (
            self._table.search(query_vector)
            .where(
                f"book_id = '{book_id}' AND path_id LIKE '{path_id}%'", prefilter=True
            )
            .limit(top_k)
            .to_list()
        )

    def delete_book(self, book_id: str) -> None:
        self._table.delete(f"book_id = '{book_id}'")

    def get_chunks_by_book(self, book_id: str) -> list[dict[str, Any]]:
        """
        Retrieve all chunks for a book using LanceDB's native scanner.
        This is significantly faster than to_pandas().
        """
        return self._table.search().where(f"book_id = '{book_id}'").to_list()
