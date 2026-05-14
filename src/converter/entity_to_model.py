# src/converter/entity_to_model.py
"""Converters: SQLModel entities  →  service models.

Rules
-----
* Functions are pure (no I/O, no side effects).
* Entities stay *inside* the repository layer; nothing in ``src/model/``
  ever imports from ``src/core/`` directly.
* All functions carry full type hints and docstrings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from src.model.audit_models import AuditReportModel, FactFeedbackModel
from src.model.book_models import BookDetailModel, BookSummaryModel
from src.model.extraction_models import ExtractionJobModel, ExtractionStatusModel
from src.model.fact_models import AtomicFactModel
from src.model.section_models import FactsModel, SectionModel
from src.model.toc_node_model import TocNodeModel

if TYPE_CHECKING:
    from src.core.atomic_fact import AtomicFact
    from src.core.audit import AuditReport
    from src.core.book import Book
    from src.core.section import Section
    from src.core.toc_node import TocNode


# ---------------------------------------------------------------------------
# Book converters
# ---------------------------------------------------------------------------


def book_entity_to_summary_model(book: "Book") -> BookSummaryModel:
    """Convert a :class:`~src.core.book.Book` entity to a :class:`BookSummaryModel`.

    Args:
        book: The ORM entity fetched from the database.

    Returns:
        An immutable summary model suitable for list responses.
    """
    return BookSummaryModel(
        id=book.id,
        title=book.title,
        author=book.author,
        source_format=book.source_format,
    )


def book_entity_to_detail_model(
    book: "Book", toc: TocNodeModel, file_url: str
) -> BookDetailModel:
    """Convert a :class:`~src.core.book.Book` entity plus an already-converted
    TOC model to a :class:`BookDetailModel`.

    Args:
        book:     The ORM entity.
        toc:      The root :class:`TocNodeModel` produced by :func:`toc_node_to_model`.
        file_url: The absolute URL to download the source file (built by the router).

    Returns:
        An immutable detail model.
    """
    return BookDetailModel(
        id=book.id,
        title=book.title,
        author=book.author,
        source_format=book.source_format,
        file_url=file_url,
        toc=toc,
    )


# ---------------------------------------------------------------------------
# TOC node converters
# ---------------------------------------------------------------------------


def toc_node_to_model(node: "TocNode") -> TocNodeModel:
    """Recursively convert a :class:`~src.core.toc_node.TocNode` business object
    to an immutable :class:`TocNodeModel`.

    Args:
        node: The root (or any subtree root) ``TocNode`` to convert.

    Returns:
        A fully populated, frozen :class:`TocNodeModel`.
    """
    return TocNodeModel(
        id=node.id,
        title=node.title,
        level=node.level,
        order=node.order,
        section_id=node.section_id,
        href=node.href,
        children=[toc_node_to_model(child) for child in node.children],
    )


# ---------------------------------------------------------------------------
# Section converters
# ---------------------------------------------------------------------------


def section_entity_to_model(section: "Section") -> SectionModel:
    """Convert a :class:`~src.core.section.Section` entity to a :class:`SectionModel`.

    Args:
        section: The ORM entity.

    Returns:
        An immutable :class:`SectionModel`.  ``word_count`` is computed lazily
        via the ``@computed_field`` on the model.
    """
    return SectionModel(
        id=section.id,
        raw_text=section.raw_text,
        extraction_status=section.extraction_status,
    )


# ---------------------------------------------------------------------------
# Atomic fact converters
# ---------------------------------------------------------------------------


def atomic_fact_entity_to_model(fact: "AtomicFact") -> AtomicFactModel:
    """Convert an :class:`~src.core.atomic_fact.AtomicFact` entity to an
    :class:`AtomicFactModel`.

    The :attr:`~src.core.atomic_fact.AtomicFact.rank` ``Tier`` enum is
    unwrapped to its integer value so service models remain free of entity
    imports.

    Args:
        fact: The ORM entity.

    Returns:
        An immutable :class:`AtomicFactModel`.
    """
    return AtomicFactModel(
        id=fact.id,
        point=fact.point or "",
        rank=fact.rank.value,  # Tier → int
        reason=fact.reason or "",
        questions=list(fact.questions),
        chunk_id=fact.chunk_id,
        start_char=fact.start_char,
        end_char=fact.end_char,
    )


def facts_to_model(
    section_id: str,
    extraction_status: str,
    facts: list["AtomicFact"],
    hints: Optional[list[str]] = None,
) -> FactsModel:
    """Build a :class:`FactsModel` from a list of entity objects.

    Args:
        section_id:        The section these facts belong to.
        extraction_status: Current :class:`~src.core.enums.ExtractionStatus` value.
        facts:             List of :class:`~src.core.atomic_fact.AtomicFact` entities.
        hints:             Optional list of hint strings (from
                           :meth:`~src.services.facts_read_service.FactsReadService.get_hints`).

    Returns:
        An immutable :class:`FactsModel`.
    """
    return FactsModel(
        section_id=section_id,
        extraction_status=extraction_status,
        facts=[atomic_fact_entity_to_model(f) for f in facts],
        hints=hints or [],
    )


# ---------------------------------------------------------------------------
# Extraction job converters (in-memory job dict → model)
# ---------------------------------------------------------------------------


def job_dict_to_extraction_job_model(
    job_id: str, data: Dict[str, Any]
) -> ExtractionJobModel:
    """Convert an in-memory job-store entry to an :class:`ExtractionJobModel`.

    Args:
        job_id: UUID string that identifies the job.
        data:   The dict stored in :class:`~src.core.job_store.JobStore`.

    Returns:
        An immutable :class:`ExtractionJobModel`.

    Raises:
        KeyError: When required keys are missing from ``data``.
    """
    return ExtractionJobModel(
        job_id=job_id,
        section_id=data["section_id"],
        status=data["status"],
        created_at=data["created_at"],
        message=data.get("message"),
    )


def job_dict_to_extraction_status_model(
    job_id: str, data: Dict[str, Any]
) -> ExtractionStatusModel:
    """Convert an in-memory job-store entry to an :class:`ExtractionStatusModel`.

    Args:
        job_id: UUID string that identifies the job.
        data:   The dict stored in :class:`~src.core.job_store.JobStore`.

    Returns:
        An immutable :class:`ExtractionStatusModel`.
    """
    return ExtractionStatusModel(
        job_id=job_id,
        status=data["status"],
        progress=data.get("progress"),
        result_summary=data.get("result_summary"),
        error=data.get("error"),
        completed_at=data.get("completed_at"),
    )


# ---------------------------------------------------------------------------
# Audit report converters
# ---------------------------------------------------------------------------


def audit_report_entity_to_model(
    report: "AuditReport",
    attempt_number: int,
    fact_points: Dict[str, str],
    fact_ranks: Dict[str, int],
) -> AuditReportModel:
    """Convert an :class:`~src.core.audit.AuditReport` entity (with eager-loaded
    ``validations``) to an :class:`AuditReportModel`.

    Args:
        report:         The ORM entity (``validations`` must be loaded).
        attempt_number: Attempt number taken from the associated
                        :class:`~src.core.summary.Summary`.
        fact_points:    Mapping of ``atomic_fact_id → point`` text, used to
                        populate :attr:`FactFeedbackModel.point`.
        fact_ranks:     Mapping of ``atomic_fact_id → rank int`` (1/2/3).

    Returns:
        An immutable :class:`AuditReportModel`.
    """
    feedback = [
        FactFeedbackModel(
            fact_id=v.atomic_fact_id,
            point=fact_points.get(v.atomic_fact_id, ""),
            rank=fact_ranks.get(v.atomic_fact_id, 3),
            status=v.status.value if hasattr(v.status, "value") else str(v.status),
            evidence=v.evidence or "",
            confidence=v.confidence,
            improved=v.improved,
        )
        for v in report.validations
    ]
    return AuditReportModel(
        id=report.id,
        score=report.score,
        score_delta=report.score_delta,
        attempt_number=attempt_number,
        fact_feedback=feedback,
    )
