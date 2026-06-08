"""Chunk embedding helpers for ingestion."""

from __future__ import annotations

from typing import Any, List, Protocol

from src.domain import TextChunk


class EmbeddingClient(Protocol):
    async def async_embed(self, **kwargs: Any) -> Any: ...


async def embed_chunks(
    chunks: List[TextChunk], embedder: EmbeddingClient, batch_size: int = 100
) -> List[TextChunk]:
    """Return chunks enriched with vector embeddings."""
    enriched_chunks = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [chunk.text for chunk in batch]

        response = await embedder.async_embed(input=texts)
        vectors = response.embeddings

        for chunk, vector in zip(batch, vectors):
            enriched_chunks.append(chunk.model_copy(update={"vector": vector}))

    return enriched_chunks
