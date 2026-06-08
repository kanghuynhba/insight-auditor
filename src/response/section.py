from typing import List, Optional
from src.response.atomic_fact import AtomicFactResponse
from src.response.base import BaseSchema


class SectionResponse(BaseSchema):
    id: str
    book_id: Optional[str]
    title: str
    level: int
    order: int
    href: Optional[str]
    raw_text: Optional[str]
    extraction_status: str
    word_count: int


class FactsResponse(BaseSchema):
    section_id: str
    extraction_status: str  # "NONE"|"PENDING"|"DONE"|"ERROR"
    facts: List[AtomicFactResponse]


class HintResponse(BaseSchema):
    hint: str
