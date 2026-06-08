# audit_repo.py
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domain.audit import AuditReport
from src.domain.summary import Summary
from src.store._sql._base import Repository


class AuditReportRepository(Repository[AuditReport]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AuditReport)

    async def get_detail(self, audit_report_id: str) -> AuditReport | None:
        stmt = (
            select(AuditReport)
            .where(AuditReport.id == audit_report_id)
            .options(
                selectinload(AuditReport.summary),
                selectinload(AuditReport.validations),
            )
        )
        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def get_history_by_section(self, section_id: str) -> list[AuditReport]:
        stmt = (
            select(AuditReport)
            .join(Summary, AuditReport.summary_id == Summary.id)
            .where(Summary.section_id == section_id)
            .options(
                selectinload(AuditReport.summary),
                selectinload(AuditReport.validations),
            )
            .order_by(AuditReport.generated_at)
        )
        result = await self.session.exec(stmt)
        return list(result.all())
