"""Base repository class for common CRUD operations."""

from typing import Generic, List, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_devbench.models.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, session: AsyncSession, model: type[T]) -> None:
        """
        Initialize repository.
        
        Args:
            session: Database session
            model: SQLAlchemy model class
        """
        self.session = session
        self.model = model

    async def get(self, id: str | int) -> T | None:
        """
        Get entity by primary key.
        
        Args:
            id: Primary key value
            
        Returns:
            Entity or None if not found
        """
        return await self.session.get(self.model, id)

    async def get_all(self, limit: int | None = None, offset: int = 0) -> List[T]:
        """
        Get all entities.
        
        Args:
            limit: Maximum number of results
            offset: Number of results to skip
            
        Returns:
            List of entities
        """
        stmt = select(self.model).offset(offset)
        if limit:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, entity: T) -> T:
        """
        Create a new entity.
        
        Args:
            entity: Entity to create
            
        Returns:
            Created entity
        """
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity: T) -> T:
        """
        Update an existing entity.
        
        Args:
            entity: Entity to update
            
        Returns:
            Updated entity
        """
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity: T) -> None:
        """
        Delete an entity.
        
        Args:
            entity: Entity to delete
        """
        await self.session.delete(entity)
        await self.session.flush()
