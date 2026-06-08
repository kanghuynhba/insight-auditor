"""Fact extraction read facade."""

from __future__ import annotations

from src.extraction._facts import get_facts_by_section
from src.extraction._models import FactsModel
from src.store import Store


class FactExtraction:
    """Public interface for reading section facts.

    Fact extraction is executed by durable ProcessingJob workers.
    """

    def __init__(self, store: Store, *_args, **_kwargs) -> None:
        self.store = store

    async def get_facts(self, section_id: str) -> FactsModel:
        return await get_facts_by_section(self.store, section_id)
