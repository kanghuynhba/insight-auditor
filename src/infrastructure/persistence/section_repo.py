# src/infrastructure/persistence/section_repo.py

from typing import List

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.models import Chapter, Section

from .base_repository import Repository


class SectionRepository(Repository[Section]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Section)

    async def find_by_chapter(self, chapter_id: str) -> List[Section]:
        statement = select(Section).where(Section.chapter_id == chapter_id)
        result = await self.session.exec(statement)
        return result.all()

    async def find_by_book(self, book_id: str) -> List[Section]:
        statement = (
            select(Section)
            .join(Chapter, Section.chapter_id == Chapter.id)
            .where(Chapter.book_id == book_id)
        )
        result = await self.session.exec(statement)
        return result.all()

    async def get_ids_by_book(self, book_id: str) -> List[str]:
        """
        Fetches only the section IDs for a book.
        Highly efficient for orchestration tasks.
        """
        statement = (
            select(Section.id)
            .join(Chapter, Section.chapter_id == Chapter.id)
            .where(Chapter.book_id == book_id)
        )
        result = await self.session.exec(statement)
        return list(result.all())
