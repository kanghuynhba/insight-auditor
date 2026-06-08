# src/response/atomic_fact.py
from typing import List, Optional
from src.domain.atomic_fact import AtomicFact
from src.response.base import BaseSchema


class AtomicFactResponse(BaseSchema):
    """Full atomic fact for client-side review."""

    id: str
    point: str
    rank: int  # 1|2|3
    reason: str
    questions: List[str]
    chunk_id: str
    start_char: Optional[int]
    end_char: Optional[int]

    @classmethod
    def from_atomic_fact(cls, atomic_fact: "AtomicFact") -> "AtomicFactResponse":
        return cls(
            id=atomic_fact.id,
            point=atomic_fact.point or "",
            rank=atomic_fact.rank.value,
            reason=atomic_fact.reason or "",
            questions=atomic_fact.questions,
            chunk_id=atomic_fact.chunk_id,
            start_char=atomic_fact.start_char,
            end_char=atomic_fact.end_char,
        )
