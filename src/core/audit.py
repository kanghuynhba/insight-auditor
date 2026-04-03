# src/core/audit.py

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field
from src.core.enums import FactStatus
from src.core.helpers import _new_id, _now


class UserSummary(BaseModel):
    id: str = Field(default_factory=_new_id)
    section_id: str
    text: str
    word_count: int
    attempt_number: int = 1
    submmited_at: datetime = Field(default_factory=_now)
    model_config = {"frozen": True}


class FactValidation(BaseModel):
    fact_id: str
    status: FactStatus
    evidence: str
    confidence: float


class AuditReport(BaseModel):
    id: str = Field(default_factory=_new_id)
    summary_id: str
    section_id: str
    score: float = 0.0
    mastered: list[str] = []
    omissions: list[str] = []
    misconceptions: list[str] = []
    score_delta: float | None = None
    generated_at: datetime = Field(default_factory=_now)
    model_config = {"frozen": True}
