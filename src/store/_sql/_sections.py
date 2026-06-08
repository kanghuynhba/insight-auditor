# src/infrastructure/persistence/section_repo.py

from sqlmodel.ext.asyncio.session import AsyncSession
from src.domain.section import Section


from src.store._sql._base import Repository


class SectionRepository(Repository[Section]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Section)
