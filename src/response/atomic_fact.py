from typing import List, Optional
from datetime import datetime
from src.response.base import BaseSchema


class AtomicFactResponse(BaseSchema):
    """Represents an atomic fact (no section text)."""

    id: str
    chunk_id: str
    path_id: str
    point: str
    reason: Optional[str]
    rank: int
    questions: List[str]
    start_char: Optional[int]
    end_char: Optional[int]
    created_at: datetime
