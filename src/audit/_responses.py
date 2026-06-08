"""Response mapping for audit routes."""

from typing import List

from src.audit._models import AuditReportModel
from src.response.audit_report import AuditReportResponse, FactFeedback
from src.response.section import HintResponse


def hints_response(hints: List[str]) -> List[HintResponse]:
    return [HintResponse(hint=hint) for hint in hints]


def audit_report_response(model: AuditReportModel) -> AuditReportResponse:
    return AuditReportResponse(
        id=model.id,
        summary_id=model.summary_id,
        score=model.score,
        score_delta=model.score_delta,
        attempt_number=model.attempt_number,
        fact_feedback=[
            FactFeedback(
                fact_id=feedback.fact_id,
                point=feedback.point,
                rank=feedback.rank,
                status=feedback.status,
                evidence=feedback.evidence,
                confidence=feedback.confidence,
                improved=feedback.improved,
            )
            for feedback in model.fact_feedback
        ],
    )
