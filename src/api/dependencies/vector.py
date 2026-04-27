from src.core.config import get_settings
from src.infrastructure.adapters.vectors.vector_database_context import (
    VectorDatabaseContext,
)
from src.infrastructure.persistence.vector_base_repository import VectorRepository
from src.infrastructure.persistence.chunk_repo import ChunkRepository

settings = get_settings()
_vector_ctx = VectorDatabaseContext(settings)


async def get_vector_repo() -> VectorRepository:
    return await ChunkRepository.create(settings, _vector_ctx)
