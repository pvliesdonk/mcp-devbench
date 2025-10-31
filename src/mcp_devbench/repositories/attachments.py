"""Repository for Attachment model operations."""

from datetime import datetime
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_devbench.models.attachments import Attachment

from .base import BaseRepository


class AttachmentRepository(BaseRepository[Attachment]):
    """Repository for attachment CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        """
        Initialize attachment repository.

        Args:
            session: Database session
        """
        super().__init__(session, Attachment)

    async def get_by_container(self, container_id: str) -> List[Attachment]:
        """
        Get all attachments for a container.

        Args:
            container_id: Container ID

        Returns:
            List of attachments
        """
        stmt = select(Attachment).where(Attachment.container_id == container_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_container(self, container_id: str) -> List[Attachment]:
        """
        Get active (not detached) attachments for a container.

        Args:
            container_id: Container ID

        Returns:
            List of active attachments
        """
        stmt = select(Attachment).where(
            Attachment.container_id == container_id, Attachment.detached_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_session(
        self, container_id: str, session_id: str
    ) -> Attachment | None:
        """
        Get attachment by container and session ID.

        Args:
            container_id: Container ID
            session_id: Session ID

        Returns:
            Attachment or None if not found
        """
        stmt = select(Attachment).where(
            Attachment.container_id == container_id,
            Attachment.session_id == session_id,
            Attachment.detached_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def detach(self, attachment_id: int) -> Attachment | None:
        """
        Mark attachment as detached.

        Args:
            attachment_id: Attachment ID

        Returns:
            Updated attachment or None if not found
        """
        attachment = await self.get(attachment_id)
        if attachment and attachment.detached_at is None:
            attachment.detached_at = datetime.utcnow()
            await self.session.flush()
            await self.session.refresh(attachment)
        return attachment

    async def detach_all_for_container(self, container_id: str) -> int:
        """
        Detach all active attachments for a container.

        Args:
            container_id: Container ID

        Returns:
            Number of attachments detached
        """
        attachments = await self.get_active_by_container(container_id)
        count = 0
        for attachment in attachments:
            attachment.detached_at = datetime.utcnow()
            count += 1
        await self.session.flush()
        return count
