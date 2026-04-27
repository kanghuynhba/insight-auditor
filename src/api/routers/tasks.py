# api/routers/tasks.py
from fastapi import APIRouter, Depends, HTTPException
from src.api.dependencies.services import get_task_service
from src.services.task_service import TaskService
from src.response.task import TaskResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, task_service: TaskService = Depends(get_task_service)):
    task = await task_service.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return TaskResponse(
        task_id=task.id,
        type=task.task_type,
        section_id=task.resource_id,
        status=task.status.value,
        created_at=task.created_at,
        completed_at=task.completed_at,
        error=task.error_message,
    )
