# src/api/dependencies/vector.py
from src.domain.config import get_settings
from src.store._vector import (
    ChunkRepository,
    VectorDatabaseContext,
    VectorRepository,
)

settings = get_settings()
_vector_ctx = VectorDatabaseContext(settings)
_chunk_repo: VectorRepository = None  # Singleton cache


async def get_vector_repo() -> VectorRepository:
    global _chunk_repo
    if _chunk_repo is None:
        _chunk_repo = await ChunkRepository.create(settings, _vector_ctx)
    return _chunk_repo
