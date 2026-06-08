"""Models returned by the extraction module."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class AtomicFactModel(BaseModel):
    id: str
    point: str
    rank: int
    reason: str
    questions: List[str]
    chunk_id: str
    start_char: Optional[int] = None
    end_char: Optional[int] = None

    model_config = {"frozen": True}


class FactsModel(BaseModel):
    section_id: str
    extraction_status: str
    facts: List[AtomicFactModel]
    hints: List[str] = []

    model_config = {"frozen": True}
