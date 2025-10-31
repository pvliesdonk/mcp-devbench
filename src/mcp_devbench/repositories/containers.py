"""Repository for Container model operations."""

from datetime import datetime
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_devbench.models.containers import Container

from .base import BaseRepository


class ContainerRepository(BaseRepository[Container]):
    """Repository for container CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize container repository.
        
        Args:
            session: Database session
        """
        super().__init__(session, Container)

    async def get_by_docker_id(self, docker_id: str) -> Container | None:
        """
        Get container by Docker ID.
        
        Args:
            docker_id: Docker container ID
            
        Returns:
            Container or None if not found
        """
        stmt = select(Container).where(Container.docker_id == docker_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_alias(self, alias: str) -> Container | None:
        """
        Get container by alias.
        
        Args:
            alias: Container alias
            
        Returns:
            Container or None if not found
        """
        stmt = select(Container).where(Container.alias == alias)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_identifier(self, identifier: str) -> Container | None:
        """
        Get container by ID or alias.
        
        Args:
            identifier: Container ID or alias
            
        Returns:
            Container or None if not found
        """
        # Try by ID first
        container = await self.get(identifier)
        if container:
            return container

        # Try by alias
        return await self.get_by_alias(identifier)

    async def list_by_status(
        self, status: str | None = None, include_stopped: bool = False
    ) -> List[Container]:
        """
        List containers by status.
        
        Args:
            status: Filter by specific status
            include_stopped: Include stopped containers
            
        Returns:
            List of containers
        """
        stmt = select(Container)

        if status:
            stmt = stmt.where(Container.status == status)
        elif not include_stopped:
            stmt = stmt.where(Container.status == "running")

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def update_status(self, container_id: str, status: str) -> Container | None:
        """
        Update container status.
        
        Args:
            container_id: Container ID
            status: New status
            
        Returns:
            Updated container or None if not found
        """
        container = await self.get(container_id)
        if container:
            container.status = status
            container.last_seen = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(container)
        return container

    async def update_last_seen(self, container_id: str) -> Container | None:
        """
        Update container's last_seen timestamp.
        
        Args:
            container_id: Container ID
            
        Returns:
            Updated container or None if not found
        """
        container = await self.get(container_id)
        if container:
            container.last_seen = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(container)
        return container

    async def get_transient_old(self, days: int) -> List[Container]:
        """
        Get transient containers older than specified days.
        
        Args:
            days: Number of days
            
        Returns:
            List of old transient containers
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = select(Container).where(
            Container.persistent.is_(False), Container.last_seen < cutoff
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
