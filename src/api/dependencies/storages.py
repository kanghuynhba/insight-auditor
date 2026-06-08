from collections.abc import AsyncGenerator
from fastapi import Depends
from src.api.dependencies.database import get_db_context
from src.store._sql import DatabaseContext
from sqlmodel.ext.asyncio.session import AsyncSession


async def get_session(
    db: DatabaseContext = Depends(get_db_context),
) -> AsyncGenerator[AsyncSession, None]:
    async with db.get_session() as session:
        yield session
