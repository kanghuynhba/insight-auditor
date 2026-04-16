# src/infrastructure/persistence/chapter_repo.py

from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.models import Chapter

from .base_repository import Repository


class ChapterRepository(Repository[Chapter]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Chapter)
