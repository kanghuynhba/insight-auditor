# src/infrastructure/persistence/book_repo.py
from typing import Optional, override
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.section import Section
from src.core.book import Book
from .base_repository import Repository


class BookRepository(Repository[Book]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Book)

    @override
    async def find_by_id(self, book_id: str) -> Optional[Book]:
        """Find book by ID - simple query without relationships."""
        stmt = select(Book).where(Book.id == book_id)
        result = await self.session.exec(stmt)
        return result.one_or_none()

    @override
    async def find_all(self) -> list[Book]:
        """Find all books ordered by creation date."""
        stmt = select(Book).order_by(Book.created_at.desc())
        result = await self.session.exec(stmt)
        return list(result.all())
