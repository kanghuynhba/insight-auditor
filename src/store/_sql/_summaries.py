from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.domain.summary import Summary
from src.store._sql._base import Repository


class SummaryRepository(Repository[Summary]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Summary)

    async def get_latest_attempt(self, section_id: str) -> int:
        statement = (
            select(Summary)
            .where(Summary.section_id == section_id)
            .order_by(Summary.attempt_number.desc())
        )
        result = await self.session.exec(statement)
        latest = result.first()
        return latest.attempt_number if latest else 0

    async def get_by_section(self, section_id: str) -> list[Summary]:
        statement = select(Summary).where(Summary.section_id == section_id)
        result = await self.session.exec(statement)
        return list(result.all())
