# src/index/operations/embed_chunks.py

from typing import List

from src.core.text_chunk import TextChunk
from src.infrastructure.llm.embedding.embedding import LLMEmbedding


async def embed_chunks(
    chunks: List[TextChunk], embedder: "LLMEmbedding", batch_size: int = 100
) -> List[TextChunk]:
    """Operation to enrich text chunks with vector embeddings."""
    enriched_chunks = []
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c.text for c in batch]

        response = await embedder.embed(input=texts)
        vectors = response.embeddings

        for chunk, vector in zip(batch, vectors):
            enriched_chunks.append(chunk.model_copy(update={"vector": vector}))

    return enriched_chunks
