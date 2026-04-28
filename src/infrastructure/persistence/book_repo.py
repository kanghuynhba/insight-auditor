# src/infrastructure/persistence/book_repo.py

from typing import Optional, override
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.table_of_content import TableOfContent
from src.core.book import Book

from .base_repository import Repository


class BookRepository(Repository[Book]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Book)

    @override
    async def find_by_id(self, book_id: str) -> Optional[Book]:
        statement = (
            select(Book)
            .where(Book.id == book_id)
            .options(
                selectinload(Book.toc)  # ← this forces loading the entire toc list
            )
        )
        result = await self.session.exec(statement)
        book = result.one_or_none()
        if book:
            # If you want to sort by order (already in relationship, but double-check)
            book.toc.sort(key=lambda t: t.order)
        return book
