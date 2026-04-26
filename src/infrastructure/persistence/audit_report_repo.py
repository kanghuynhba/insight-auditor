# audit_repo.py
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.audit import AuditReport
from src.infrastructure.persistence.base_repository import Repository


class AuditReportRepository(Repository[AuditReport]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AuditReport)

    async def get_history_by_section(self, section_id: str) -> list[AuditReport]:
        statement = select(AuditReport).where(AuditReport.section_id == section_id)
        result = await self.session.exec(statement)
        return list(result.all())
