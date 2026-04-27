# src/core/task.py
from datetime import datetime
from typing import Optional
from sqlalchemy import JSON
from sqlmodel import Field, Column
from src.core.enums import TaskStatus
from src.core.entity import Entity


class Task(Entity, table=True):
    __tablename__ = "task"

    # "fact_extraction", "book_ingestion", ...
    task_type: str = Field(index=True)
    # "section", "book", "chapter" — the entity being worked on
    resource_type: str = Field(index=True)
    # UUID of that entity, no FK constraint
    resource_id: str = Field(index=True)

    status: TaskStatus = Field(default=TaskStatus.PENDING)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    # input params
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # output summary
    result: dict = Field(default_factory=dict, sa_column=Column(JSON))
