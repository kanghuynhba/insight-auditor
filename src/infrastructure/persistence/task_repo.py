# src/infrastructure/persistence/book_repo.py

from typing import Optional
from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.enums import TaskStatus
from src.core.task import Task

from .base_repository import Repository


class TaskRepository(Repository[Task]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Task)

    async def count_pending_by_section(self, section_id: str) -> int:
        stmt = select(func.count()).where(
            Task.section_id == section_id,
            Task.status.in_([TaskStatus.PENDING]),
        )
        result = await self.session.exec(stmt)
        return result.one()

    async def find_latest(
        self,
        resource_type: str,
        resource_id: str,
        task_type: Optional[str] = None,
    ) -> Optional[Task]:
        stmt = (
            select(Task)
            .where(Task.resource_type == resource_type, Task.resource_id == resource_id)
            .order_by(Task.created_at.desc())
            .limit(1)
        )
        if task_type:
            stmt = stmt.where(Task.task_type == task_type)
        result = await self.session.exec(stmt)
        return result.first()
