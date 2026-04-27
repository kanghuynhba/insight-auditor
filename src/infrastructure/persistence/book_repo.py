# src/infrastructure/persistence/book_repo.py

from typing import Optional, override
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.models import Book, Chapter

from .base_repository import Repository


class BookRepository(Repository[Book]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Book)

    @override
    async def find_by_id(self, book_id: str) -> Optional[Book]:
        """Override to eagerly load chapters and sections."""
        statement = (
            select(Book)
            .where(Book.id == book_id)
            .options(selectinload(Book.chapters).selectinload(Chapter.sections))
        )
        result = await self.session.exec(statement)
        return result.one_or_none()
