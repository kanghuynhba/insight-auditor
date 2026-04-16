# src/infrastructure/persistence/chunk_repo.py
import threading
import time
from typing import Any

import lancedb
from lancedb.pydantic import LanceModel, Vector
from lancedb.table import LanceTable
from openai import AzureOpenAI, RateLimitError
from src.core.config import Settings
from src.infrastructure.adapters.vectors.vector_store import VectorStore
from src.infrastructure.chunking.text_chunk import TextChunk


class ChunkSchema(LanceModel):
    id: str
    book_id: str
    section_id: str
    path_id: str
    text: str
    vector: Vector(1536)
    start_char: int
    end_char: int
    chunk_index: int
    chunk_level: str
    word_count: int
    context_text: str | None


class ChunkRepository(VectorStore):
    def __init__(self, settings: Settings):
        self._openai = AzureOpenAI(
            api_key=settings.azure_openai_api_key.get_secret_value(),
            azure_endpoint=str(settings.azure_openai_endpoint),
            api_version=str(settings.openai_api_version),
        )
        self._embedding_model = str(settings.embedding_model)
        self._db = lancedb.connect(str(settings.lance_db_path))
        self.table_name = settings.vector_index_name
        self._table = self._init_table()
        self._write_lock = threading.Lock()

    def _init_table(self) -> "LanceTable":
        if self.table_name in self._db.list_tables():
            return self._db.open_table(self.table_name)
        return self._db.create_table(
            self.table_name,
            schema=ChunkSchema,
            mode="overwrite",
        )

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
                except RateLimitError:
                    if attempt == 2:
                        raise
                    time.sleep(2**attempt)  # 1s, 2s backoff
        return all_embeddings

    def save_chunks(self, chunks: list[TextChunk]) -> None:
        texts = [chunk.text for chunk in chunks]
        vectors = self._embed(texts)

        data = []
        for chunk, vector in zip(chunks, vectors):
            row = chunk.model_dump()
            row["vector"] = vector
            data.append(row)

        with self._write_lock:  # ← serialize writes, parallelize embeddings
            self._table.add(data)

    def search_chunks(
        self, query: str, book_id: str, path_id: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        query_vector = self._embed([query])[0]
        where_filter = f"book_id = '{book_id}' AND path_id LIKE '{path_id}%'"

        return (
            self._table.search(query_vector)
            .where(where_filter, prefilter=True)
            .limit(top_k)
            .to_list()
        )

    def delete_book(self, book_id: str) -> None:
        self._table.delete(f"book_id = '{book_id}'")

    async def get_chunks_by_book(self, book_id: str) -> list[dict[str, Any]]:
        """Retrieve all chunks belonging to a given book."""
        import asyncio

        def _sync_query():
            # This bypasses vector search entirely.
            df = self._table.to_pandas()
            # Filter rows where book_id matches
            filtered_df = df[df["book_id"] == book_id]

            # Convert back to list of dicts
            return filtered_df.to_dict(orient="records")

        return await asyncio.to_thread(_sync_query)
