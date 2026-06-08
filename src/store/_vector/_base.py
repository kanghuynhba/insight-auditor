# src/infrastructure/persistence/vector_base_repository.py
from abc import ABC, abstractmethod
from typing import Any, List

from src.domain.text_chunk import TextChunk


class VectorRepository(ABC):
    """The base class for vector storage data-access classes."""

    @abstractmethod
    async def save_chunks(self, chunks: list[TextChunk]) -> None:
        """Persists text embeddings to the vector store."""
        pass

    @abstractmethod
    async def search_chunks(
        self, query_vector: list[float], book_id: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Performs semantic search against chunks."""
        pass

    @abstractmethod
    async def get_chunks_by_book(self, book_id: str) -> List[TextChunk]:
        """
        NEW: Mandatory method for all vector providers.
        Retrieves all chunks belonging to a given book.
        """
        pass

    @abstractmethod
    async def delete_book(self, book_id: str) -> None:
        """Deletes all chunks associated with a specific book."""
        pass

    @abstractmethod
    async def get_chunks_by_section(self, section_id: str) -> List[TextChunk]:
        """Retrieves all chunks belonging to a given section."""
        pass
