# src/model/audit_models.py
"""Service models for audit / evaluation results."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class FactFeedbackModel(BaseModel):
    """Per-fact feedback produced during an evaluation."""

    fact_id: str
    point: str
    rank: int
    status: str  # "found" | "partial" | "missing" | "contradicted"
    evidence: Optional[str] = None
    confidence: float
    improved: Optional[bool] = None

    model_config = {"frozen": True}


class AuditReportModel(BaseModel):
    """Service model returned by :class:`~src.services.audit_service.AuditService`."""

    id: str
    score: float
    score_delta: Optional[float] = None
    attempt_number: int
    fact_feedback: List[FactFeedbackModel]

    model_config = {"frozen": True}
