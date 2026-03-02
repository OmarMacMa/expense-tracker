import uuid
from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Base

T = TypeVar("T", bound=Base)


class SpaceScopedRepository(Generic[T]):
    """Base repository that auto-injects space_id into every query."""

    def __init__(self, session: AsyncSession, space_id: uuid.UUID, model: type[T]):
        self._session = session
        self._space_id = space_id
        self._model = model

    async def get_by_id(self, id: uuid.UUID) -> T | None:
        """Get by ID within the current space. Never fetches by PK alone."""
        stmt = select(self._model).where(
            self._model.space_id == self._space_id,
            self._model.id == id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> Sequence[T]:
        """List all records in the current space."""
        stmt = select(self._model).where(self._model.space_id == self._space_id)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def create(self, entity: T) -> T:
        """Create a new entity, ensuring space_id is set."""
        entity.space_id = self._space_id
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def delete_by_id(self, id: uuid.UUID) -> bool:
        """Delete by ID within the current space. Returns True if deleted."""
        stmt = delete(self._model).where(
            self._model.space_id == self._space_id,
            self._model.id == id,
        )
        result = await self._session.execute(stmt)
        return result.rowcount > 0
