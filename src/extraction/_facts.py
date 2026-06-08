"""Read helpers for extracted facts."""

from __future__ import annotations

from src.domain import AtomicFact, ExtractionNotReadyError, ExtractionStatus
from src.extraction._models import AtomicFactModel, FactsModel
from src.store import Store


async def get_facts_by_section(store: Store, section_id: str) -> FactsModel:
    section = await store.get_section(section_id)
    if not section:
        raise ValueError(f"Section {section_id} not found")
    if section.extraction_status != ExtractionStatus.DONE:
        raise ExtractionNotReadyError(
            status=section.extraction_status,
            message="No facts extracted yet",
        )

    facts = await store.get_facts_by_section(section_id)
    return FactsModel(
        section_id=section_id,
        extraction_status=ExtractionStatus.DONE,
        facts=[atomic_fact_model(fact) for fact in facts],
        hints=[],
    )


def atomic_fact_model(fact: AtomicFact) -> AtomicFactModel:
    return AtomicFactModel(
        id=fact.id,
        point=fact.point or "",
        rank=fact.rank.value,
        reason=fact.reason or "",
        questions=list(fact.questions),
        chunk_id=fact.chunk_id,
        start_char=fact.start_char,
        end_char=fact.end_char,
    )
