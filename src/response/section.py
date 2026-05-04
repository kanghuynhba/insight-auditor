from typing import Optional
from src.response.base import BaseSchema


class SectionDetailResponse(BaseSchema):
    """Full section including raw_text and extraction_status."""

    id: str
    raw_text: Optional[str]
    extraction_status: str
