# src/core/interfaces.py

from abc import ABC, abstractmethod

from src.core.models import Section, Chapter
from src.core.atomic_fact import AtomicFact
from src.core.audit import UserSummary, FactValidation, AuditReport

class LLMInterface(ABC):
    """Contract for all Generative AI operations."""

    @abstractmethod
    def generate_atomic_facts(self, text: str, path_id: str) -> list[AtomicFact]:
        """Extracts T1/T2/T3 facts from raw text."""
        pass

    @abstractmethod
    def validate_facts(self, summary: str, facts: list[AtomicFact]) -> list[FactValidation]:
        """Compares user summary against a list of facts (Entailment)."""
        pass

    @abstractmethod
    def generate_hints(self, facts: list[AtomicFact], count: int) -> list[str]:
        """Creates study hints based on missing facts."""
        pass

    @abstractmethod
    def generate_structural_map(self, text: str) -> str:
        """Generates a high-level outline/summary for a Chapter."""
        pass

class VectorRepository(ABC):
    """Contract for semantic search (ChromaDB, Pinecone, etc.)."""

    @abstractmethod
    def save_chunks(self, book_id: str, chunks: list[dict]) -> None:
        """Persists text embeddings to the vector store."""
        pass

    @abstractmethod
    def search_chunks(self, query: str, path_filter: str, top_k: int) -> list[dict]:
        """Performs semantic search restricted by a specific path_id prefix."""
        pass

class AtomicFactRepository(ABC):
    """Contract for storing the 'Source of Truth' facts (SQLite/Postgres)."""

    @abstractmethod
    def save_facts(self, facts: list[AtomicFact]) -> None:
        """Batch saves extracted facts."""
        pass

    @abstractmethod
    def get_facts_by_path(self, path_id: str) -> list[AtomicFact]:
        """Retrieves facts for a specific section or an entire chapter (prefix match)."""
        pass

class SummaryRepository(ABC):
    """Contract for tracking user submissions and attempt counts."""

    @abstractmethod
    def save_summary(self, summary: UserSummary) -> None:
        """Persists a user's summary attempt."""
        pass

    @abstractmethod
    def get_latest_attempt(self, section_id: str) -> int:
        """Returns the highest attempt_number for a section to increment for the next."""
        pass

class AuditRepository(ABC):
    """Contract for storing final scored reports."""

    @abstractmethod
    def save_report(self, report: AuditReport) -> None:
        """Persists the final audit results."""
        pass

    @abstractmethod
    def get_history_by_section(self, section_id: str) -> list[AuditReport]:
        """Retrieves all previous scores for progress visualization."""
        pass
