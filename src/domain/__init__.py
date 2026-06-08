"""Public domain module.

This package owns entities, enums, exceptions, configuration, and small domain
helpers. Importing it also registers SQLModel table classes for mapper setup.
"""

from src.domain.atomic_fact import AtomicFact
from src.domain.audit import AuditReport
from src.domain.book import Book
from src.domain.config import Settings, get_settings
from src.domain.entity import Entity
from src.domain.enums import ExtractionStatus, FactStatus, Tier
from src.domain.exceptions import (
    AuditGateError,
    BookNotFoundError,
    ExtractionNotReadyError,
    IngestionError,
    SectionNotFoundError,
    UnsupportedFormatError,
)
from src.domain.fact_validation import FactValidationResult
from src.domain.helpers import new_id, now, word_count
from src.domain.processing_job import ProcessingJob
from src.domain.section import Section
from src.domain.summary import Summary
from src.domain.text_chunk import TextChunk
from src.domain.toc_node import TocNode
from src.domain.tokenizer import count_tokens

__all__ = [
    "AtomicFact",
    "AuditGateError",
    "AuditReport",
    "Book",
    "BookNotFoundError",
    "Entity",
    "ExtractionNotReadyError",
    "ExtractionStatus",
    "FactStatus",
    "FactValidationResult",
    "IngestionError",
    "ProcessingJob",
    "Section",
    "SectionNotFoundError",
    "Settings",
    "Summary",
    "TextChunk",
    "Tier",
    "TocNode",
    "UnsupportedFormatError",
    "count_tokens",
    "get_settings",
    "new_id",
    "now",
    "word_count",
]
