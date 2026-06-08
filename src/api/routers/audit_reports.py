"""Audit report router."""

from fastapi import APIRouter, Depends, HTTPException

from src.api.dependencies.wiring import get_audit_gateway
from src.audit import AuditGateway, audit_report_response
from src.response.audit_report import AuditReportResponse

router = APIRouter(prefix="/audit_reports", tags=["audit_reports"])


@router.get("/{audit_report_id}", response_model=AuditReportResponse)
async def get_audit_report(
    audit_report_id: str,
    audit: AuditGateway = Depends(get_audit_gateway),
) -> AuditReportResponse:
    report = await audit.get_report(audit_report_id)
    if not report:
        raise HTTPException(404, "Audit report not found")
    return audit_report_response(report)
