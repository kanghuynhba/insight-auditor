# src/services/task_service.py

import logging
from datetime import datetime, timezone
from typing import Dict, Set, Optional
from src.core.enums import TaskStatus
from src.core.task import Task
from src.infrastructure.persistence.task_repo import TaskRepository

logger = logging.getLogger(__name__)


class TaskService:
    """
    Optional tracking layer for any long-running operation.
    Inject it into a service when you want observability; omit it when you don't.
    All task DB writes go through here — domain services never touch task_repo directly.
    """

    def __init__(self, task_repo: TaskRepository):
        self._repo = task_repo

    # Map resource_type -> set of allowed task_type values
    ALLOWED_TASKS: Dict[str, Set[str]] = {
        "section": {"fact_extraction"},
        "book": {"book_ingestion", "regenerate_structural_maps"},
        "chapter": {"structural_map_generation"},
    }

    def validate_task(self, resource_type: str, task_type: str) -> bool:
        allowed = self.ALLOWED_TASKS.get(resource_type)
        if not allowed:
            return False
        return task_type in allowed

    async def create(
        self,
        task_type: str,
        resource_type: str,
        resource_id: str,
        payload: Optional[dict] = None,
    ) -> Task:
        """Create and persist a new PENDING task. Returns it so caller gets the task_id."""
        if not self.validate_task(resource_type, task_type):
            raise ValueError(
                f"Task type '{task_type}' not allowed for resource type '{resource_type}'"
            )
        task = Task(
            task_type=task_type,
            resource_type=resource_type,
            resource_id=resource_id,
            status=TaskStatus.PENDING,
            payload=payload or {},
        )
        await self._repo.save(task)
        await self._repo.session.commit()
        return task

    async def start(self, task_id: str) -> None:
        await self._update(task_id, status=TaskStatus.RUNNING)

    async def done(self, task_id: str, result: Optional[dict] = None) -> None:
        await self._update(task_id, status=TaskStatus.DONE, result=result)

    async def error(self, task_id: str, exc: Exception) -> None:
        await self._update(task_id, status=TaskStatus.ERROR, error_message=str(exc))

    async def get(self, task_id: str) -> Optional[Task]:
        return await self._repo.find_by_id(task_id)

    async def get_latest_for_resource(
        self,
        resource_type: str,
        resource_id: str,
        task_type: Optional[str] = None,
    ) -> Optional[Task]:
        """Useful for checking if a resource already has a running task."""
        return await self._repo.find_latest(resource_type, resource_id, task_type)

    async def _update(self, task_id, status, result=None, error_message=None) -> None:
        try:
            task = await self._repo.find_by_id(task_id)
            if not task:
                logger.warning(f"TaskService: task {task_id} not found")
                return
            task.status = status
            if status == TaskStatus.RUNNING and not task.started_at:
                task.started_at = datetime.now(timezone.utc)
            elif (
                status in (TaskStatus.DONE, TaskStatus.ERROR) and not task.completed_at
            ):
                task.completed_at = datetime.now(timezone.utc)
            if result:
                task.result = result
            if error_message:
                task.error_message = error_message
            await self._repo.save(task)
            await self._repo.session.commit()
        except Exception:
            logger.exception(
                f"TaskService: failed to update task {task_id} to {status}"
            )
