from typing import Optional
from src.response.base import BaseSchema


class SectionDetailResponse(BaseSchema):
    """Full section including raw_text and extraction_status."""

    id: str
    title: str
    path_id: str
    level: int
    word_count: int
    raw_text: Optional[str]
    chapter_id: str
    extraction_status: str
