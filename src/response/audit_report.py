from typing import List, Optional
from datetime import datetime
from src.response.base import BaseSchema


class FactFeedback(BaseSchema):
    fact_id: str
    point: str
    rank: int
    status: str
    evidence: Optional[str]
    confidence: float
    improved: Optional[bool]


class AuditReportResponse(BaseSchema):
    id: str
    summary_id: str
    score: float
    score_delta: Optional[float]
    attempt_number: int
    fact_feedback: List[FactFeedback]


class SummarySubmissionResponse(BaseSchema):
    summary_id: str
    audit_report_id: str
