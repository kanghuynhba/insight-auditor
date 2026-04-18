# src/infrastructure/persistence/chunk_repo.py
import threading
import time
from typing import Any

import lancedb
from lancedb.table import LanceTable
from openai import (
    APIConnectionError,
    APITimeoutError,
    AzureOpenAI,
    InternalServerError,
    RateLimitError,
)
from src.core.config import Settings
from src.infrastructure.adapters.mariadb.vector_database_context import (
    VectorDatabaseContext,
)
from src.infrastructure.chunking.text_chunk import TextChunk
from src.infrastructure.persistence.vector_base_repository import VectorRepository


class ChunkRepository(VectorRepository):
    def __init__(self, settings: Settings, table: "LanceTable"):
        self._openai = AzureOpenAI(
            api_key=settings.azure_openai_api_key.get_secret_value(),
            azure_endpoint=str(settings.azure_openai_endpoint),
            api_version=str(settings.openai_api_version),
        )
        self._embedding_model = str(settings.embedding_model)
        self._table = table
        self._write_lock = threading.Lock()

    @classmethod
    async def create(cls, settings: Settings, vector_ctx: VectorDatabaseContext):
        table = await vector_ctx.get_table(settings.vector_index_name)
        return cls(settings, table)

    def _embed(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            for attempt in range(3):
                try:
                    response = self._openai.embeddings.create(
                        model=self._embedding_model,
                        input=batch,
                    )
                    all_embeddings.extend(item.embedding for item in response.data)
                    break
                except (
                    RateLimitError,
                    APIConnectionError,
                    APITimeoutError,
                    InternalServerError,
                ) as e:
                    if attempt == 2:
                        raise
                    time.sleep(2**attempt)
        return all_embeddings

    def save_chunks(self, chunks: list[TextChunk]) -> None:
        texts = [chunk.text for chunk in chunks]
        vectors = self._embed(texts)

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
        query_vector = self._embed([query])[0]
        where_filter = "book_id = ? AND path_id LIKE ?".where(
            where_filter, [book_id, f"{path_id}%"], prefilter=True
        )
        return (
            self._table.search(query_vector)
            .where(where_filter, prefilter=True)
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
