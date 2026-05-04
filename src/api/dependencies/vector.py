# src/api/dependencies/vector.py
from src.core.config import get_settings
from src.infrastructure.adapters.vectors.vector_database_context import (
    VectorDatabaseContext,
)
from src.infrastructure.persistence.vector_base_repository import VectorRepository
from src.infrastructure.persistence.chunk_repo import ChunkRepository

settings = get_settings()
_vector_ctx = VectorDatabaseContext(settings)
_chunk_repo: VectorRepository = None  # Singleton cache


async def get_vector_repo() -> VectorRepository:
    global _chunk_repo
    if _chunk_repo is None:
        _chunk_repo = await ChunkRepository.create(settings, _vector_ctx)
    return _chunk_repo
