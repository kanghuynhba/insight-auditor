# src/infrastructure/persistence/book_repo.py

from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.models import Book

from .base_repository import Repository


class BookRepository(Repository[Book]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Book)
