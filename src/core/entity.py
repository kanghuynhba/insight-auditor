from datetime import datetime

from sqlmodel import Field, SQLModel
from src.core.helpers import new_id, now


class Entity(SQLModel):
    id: str = Field(default_factory=new_id, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=now)
