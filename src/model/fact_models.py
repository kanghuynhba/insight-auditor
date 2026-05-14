# src/model/fact_models.py
"""Service model for an atomic fact."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class AtomicFactModel(BaseModel):
    """Immutable service model for a single atomic fact.

    ``rank`` carries the integer tier value (1=Critical, 2=Important, 3=Nuance).
    """

    id: str
    point: str
    rank: int  # 1 | 2 | 3
    reason: str
    questions: List[str]
    chunk_id: str
    start_char: Optional[int] = None
    end_char: Optional[int] = None

    model_config = {"frozen": True}
