from typing import List
from sqlmodel import select
from src.core.fact_validation import FactValidationResult
from sqlmodel.ext.asyncio.session import AsyncSession
from src.infrastructure.persistence.base_repository import Repository


class FactValidationResultRepository(Repository[FactValidationResult]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, FactValidationResult)

    async def get_fact_validation_by_atomic_facts(
        self, atomic_fact_id: str
    ) -> List[FactValidationResult]:
        statement = select(FactValidationResult).where(
            FactValidationResult.atomic_fact_id == atomic_fact_id
        )
        result = await self.session.exec(statement)
        return list(result.all())

    async def get_fact_validation_by_report(
        self, report_id: str
    ) -> List[FactValidationResult]:
        statement = select(FactValidationResult).where(
            FactValidationResult.report_id == report_id
        )
        result = await self.session.exec(statement)
        return list(result.all())
