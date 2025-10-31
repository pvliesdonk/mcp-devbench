"""Repository for Exec model operations."""

from datetime import datetime
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_devbench.models.execs import Exec

from .base import BaseRepository


class ExecRepository(BaseRepository[Exec]):
    """Repository for exec CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize exec repository.

        Args:
            session: Database session
        """
        super().__init__(session, Exec)

    async def get_by_container(self, container_id: str) -> List[Exec]:
        """
        Get all execs for a container.

        Args:
            container_id: Container ID

        Returns:
            List of execs
        """
        stmt = select(Exec).where(Exec.container_id == container_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_container(self, container_id: str) -> List[Exec]:
        """
        Get active (not completed) execs for a container.

        Args:
            container_id: Container ID

        Returns:
            List of active execs
        """
        stmt = select(Exec).where(Exec.container_id == container_id, Exec.ended_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def complete_exec(
        self, exec_id: str, exit_code: int, usage: dict | None = None
    ) -> Exec | None:
        """
        Mark exec as completed.

        Args:
            exec_id: Exec ID
            exit_code: Exit code from command
            usage: Resource usage information

        Returns:
            Updated exec or None if not found
        """
        exec_entry = await self.get(exec_id)
        if exec_entry and exec_entry.ended_at is None:
            exec_entry.ended_at = datetime.utcnow()
            exec_entry.exit_code = exit_code
            if usage:
                exec_entry.usage = usage
            await self.session.flush()
            await self.session.refresh(exec_entry)
        return exec_entry

    async def get_old_completed(self, hours: int = 24) -> List[Exec]:
        """
        Get completed execs older than specified hours.

        Args:
            hours: Number of hours

        Returns:
            List of old completed execs
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(hours=hours)
        stmt = select(Exec).where(Exec.ended_at.is_not(None), Exec.ended_at < cutoff)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
