# src/infrastructure/persistence/section_repo.py

from typing import List

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.table_of_content import TableOfContent
from src.core.section import Section


from .base_repository import Repository


class SectionRepository(Repository[Section]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Section)

    async def find_by_book(self, book_id: str) -> List[Section]:
        statement = (
            select(Section)
            .join(TableOfContent, Section.id == TableOfContent.section_id)
            .where(TableOfContent.book_id == book_id)
            .order_by(TableOfContent.order)
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_ids_by_book(self, book_id: str) -> List[str]:
        """
        Fetches only the section IDs for a book.
        Highly efficient for orchestration tasks.
        """
        statement = (
            select(Section.id)
            .join(TableOfContent, Section.id == TableOfContent.section_id)
            .where(TableOfContent.book_id == book_id)
        )
        result = await self.session.exec(statement)
        return list(result.all())
