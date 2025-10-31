"""Attachment model for tracking client attachments to containers."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Attachment(Base):
    """Model for tracking client attachments to containers."""

    __tablename__ = "attachments"

    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to container
    container_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("containers.id"), nullable=False
    )

    # Client information
    client_name: Mapped[str] = mapped_column(String(100), nullable=False)
    session_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Timestamps
    attached_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    detached_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        """String representation of Attachment."""
        return (
            f"<Attachment(id={self.id}, container_id={self.container_id}, "
            f"client_name={self.client_name}, session_id={self.session_id})>"
        )
