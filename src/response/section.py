from typing import List, Optional
from src.response.atomic_fact import AtomicFactResponse
from src.response.base import BaseSchema


class FactsResponse(BaseSchema):
    section_id: str
    extraction_status: str  # "NONE"|"PENDING"|"DONE"|"ERROR"
    facts: List[AtomicFactResponse]


class HintResponse(BaseSchema):
    hint: str
