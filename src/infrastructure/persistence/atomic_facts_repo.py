# src/infrastructure/persistence/atomic_facts_repo.py

from typing import List

from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.atomic_fact import AtomicFact

from .base_repository import Repository


class AtomicFactRepository(Repository[AtomicFact]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AtomicFact)

    async def find_by_section(self, section_id: str) -> List[AtomicFact]:
        """Custom query specific to AtomicFacts."""
        from sqlmodel import select

        statement = select(AtomicFact).where(AtomicFact.section_id == section_id)
        result = await self.session.exec(statement)
        return list(result.all())
