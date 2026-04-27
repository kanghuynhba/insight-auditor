# api/routers/tasks.py

from fastapi import Depends, HTTPException, APIRouter
from src.services.task_service import TaskService
from src.api.dependencies.services import get_task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}")
async def get_task(task_id: str, task_service: TaskService = Depends(get_task_service)):
    task = await task_service.get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return task  # or a specific TaskResponse schema
