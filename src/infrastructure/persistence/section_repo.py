# src/infrastructure/persistence/section_repo.py

from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.section import Section


from .base_repository import Repository


class SectionRepository(Repository[Section]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Section)
