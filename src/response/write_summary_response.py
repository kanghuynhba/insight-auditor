"""Response DTO for legacy summary evaluation endpoints."""

from __future__ import annotations

from typing import List, Literal, Optional

from src.response.base import BaseSchema


class FactFeedbackResponse(BaseSchema):
    """Per-fact feedback item included in a :class:`WriteSummaryResponse`."""

    fact_id: str
    point: str
    rank: int  # 1=Critical, 2=Important, 3=Nuance
    status: Literal["found", "partial", "missing", "contradicted"]
    evidence: Optional[str] = None
    confidence: float
    improved: Optional[bool] = None


class WriteSummaryResponse(BaseSchema):
    """Result returned after evaluating a user-written summary.

    ``report_id``      – database ID of the persisted :class:`AuditReport`.
    ``score``          – weighted fact-recall score (0.0 – 1.0).
    ``score_delta``    – improvement over the previous attempt, or ``None``
                         when this is the first attempt.
    ``attempt_number`` – 1-based index of this evaluation for the section.
    ``fact_feedback``  – per-fact validation details.
    """

    report_id: str
    score: float
    score_delta: Optional[float] = None
    attempt_number: int
    fact_feedback: List[FactFeedbackResponse]
