"""Base classes for vector stores."""

from abc import ABC, abstractmethod
from typing import Any

from src.infrastructure.chunking.text_chunk import TextChunk


class VectorStore(ABC):
    """The base class for vector storage data-access classes."""

    @abstractmethod
    def save_chunks(self, chunks: list[TextChunk]) -> None:
        """Persists text embeddings to the vector store."""
        pass

    @abstractmethod
    def search_chunks(
        self, query: str, book_id: str, path_id: str, top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Performs semantic search against chunks, filtered by book and section."""
        pass

    @abstractmethod
    def delete_book(self, book_id: str) -> None:
        """Deletes all chunks associated with a specific book."""
        pass
