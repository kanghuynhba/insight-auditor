# src/infrastructure/persistence/chapter_repo.py

from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.table_of_content import TableOfContent

from .base_repository import Repository


class TableOfContentRepository(Repository[TableOfContent]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, TableOfContent)
