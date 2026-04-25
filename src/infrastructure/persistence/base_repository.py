# src/infrastructure/persistence/base_repository.py
from abc import abstractmethod
from typing import Any, Generic, List, Optional, Type, TypeVar

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.core.entity import Entity

T = TypeVar("T", bound=Entity)


class Repository(Generic[T]):
    def __init__(self, session: AsyncSession, entity_class: Type[T]):
        self.session = session
        self.entity_class = entity_class

    async def save(self, entity: T) -> T:
        """Generic save: handles both INSERT and UPDATE via session.add."""
        self.session.add(entity)
        return entity

    async def save_all(self, entities: List[T]) -> List[T]:
        """
        Persists a list of entities in a single batch.
        Useful for saving AtomicFacts extracted from a chunk.
        """
        if not entities:
            return []

        self.session.add_all(entities)
        # Note: We do not commit here because the session lifecycle
        # is managed by the DatabaseContext.get_session() context manager.
        return entities

    async def find_by_id(self, entity_id: Any) -> Optional[T]:
        """Generic fetch by ID."""
        return await self.session.get(self.entity_class, entity_id)

    async def find_all(self) -> List[T]:
        """Fetch all records for this entity type."""
        statement = select(self.entity_class)
        result = await self.session.exec(statement)
        return list(result.all())

    async def delete(self, entity_id: Any) -> None:
        """Deletes an entity by its ID."""
        entity = await self.find_by_id(entity_id)
        if entity:
            await self.session.delete(entity)

    @abstractmethod
    async def get_ids_by_book(self, book_id: str) -> List[Any]:
        pass

    @abstractmethod
    async def find_by_chunk(self, chunk_id: str) -> List[Any]:
        pass
