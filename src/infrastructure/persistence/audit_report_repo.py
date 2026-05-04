# audit_repo.py
from sqlmodel.ext.asyncio.session import AsyncSession

from src.core.audit import AuditReport
from src.infrastructure.persistence.base_repository import Repository


class AuditReportRepository(Repository[AuditReport]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AuditReport)
