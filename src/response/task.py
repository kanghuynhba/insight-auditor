# src/response/task.py
from datetime import datetime
from typing import Optional
from src.response.base import BaseSchema


class TaskResponse(BaseSchema):
    task_id: str
    type: str
    section_id: str
    status: str  # "PENDING" | "DONE" | "ERROR"
    created_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str]
