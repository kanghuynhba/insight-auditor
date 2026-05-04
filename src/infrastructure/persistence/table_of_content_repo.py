# src/infrastructure/persistence/table_of_content_repo.py
from typing import List
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.table_of_content import TableOfContent
from .base_repository import Repository


class TableOfContentRepository(Repository[TableOfContent]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, TableOfContent)

    async def get_by_book(self, book_id: str) -> List[TableOfContent]:
        """Get all TOC entries for a book, ordered by order field."""
        stmt = (
            select(TableOfContent)
            .where(TableOfContent.book_id == book_id)
            .order_by(TableOfContent.order)
        )
        result = await self.session.exec(stmt)
        return list(result.all())
