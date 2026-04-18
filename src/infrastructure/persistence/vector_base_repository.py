# src/infrastructure/persistence/vector_base_repository.py
from abc import ABC, abstractmethod
from typing import Any, List

from src.infrastructure.chunking.text_chunk import TextChunk


class VectorRepository(ABC):
    """The base class for vector storage data-access classes."""

    @abstractmethod
    def save_chunks(self, chunks: list[TextChunk]) -> None:
        """Persists text embeddings to the vector store."""
        pass

    @abstractmethod
    def search_chunks(
        self, query: str, book_id: str, path_id: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Performs semantic search against chunks."""
        pass

    @abstractmethod
    async def get_chunks_by_book(self, book_id: str) -> List[dict[str, Any]]:
        """
        NEW: Mandatory method for all vector providers.
        Retrieves all chunks belonging to a given book.
        """
        pass

    @abstractmethod
    def delete_book(self, book_id: str) -> None:
        """Deletes all chunks associated with a specific book."""
        pass
