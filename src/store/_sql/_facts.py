# src/infrastructure/persistence/atomic_facts_repo.py

from typing import List

from sqlmodel import delete, select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.domain.atomic_fact import AtomicFact
from src.store._sql._base import Repository


class AtomicFactRepository(Repository[AtomicFact]):
    def __init__(self, session: AsyncSession):
        # Passes the session and model type to the base CRUD repository
        super().__init__(session, AtomicFact)

    async def find_by_section(self, section_id: str) -> List[AtomicFact]:
        """Retrieves all facts extracted from a specific section."""
        statement = select(AtomicFact).where(AtomicFact.section_id == section_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def find_by_chunk(self, chunk_id: str) -> List[AtomicFact]:
        """
        Retrieves all facts extracted from a specific LanceDB chunk.
        Crucial for preventing duplicate LLM extractions from the same chunk.
        """
        statement = select(AtomicFact).where(AtomicFact.chunk_id == chunk_id)
        result = await self.session.exec(statement)
        return list(result.all())

    async def delete_by_chunk(self, chunk_id: str) -> None:
        """Delete all atomic facts for a given chunk."""
        stmt = delete(AtomicFact).where(AtomicFact.chunk_id == chunk_id)
        await self.session.exec(stmt)
