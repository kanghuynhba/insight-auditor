"""Models returned by the audit module."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class FactFeedbackModel(BaseModel):
    fact_id: str
    point: str
    rank: int
    status: str
    evidence: Optional[str] = None
    confidence: float
    improved: Optional[bool] = None

    model_config = {"frozen": True}


class AuditReportModel(BaseModel):
    id: str
    summary_id: str
    score: float
    score_delta: Optional[float] = None
    attempt_number: int
    fact_feedback: List[FactFeedbackModel]

    model_config = {"frozen": True}
