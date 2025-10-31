"""Container model for tracking Docker containers."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Container(Base):
    """Model for tracking Docker containers managed by MCP DevBench."""

    __tablename__ = "containers"

    # Primary key - opaque ID in format "c_{uuid}"
    id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # Docker container ID
    docker_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    # User-friendly alias (optional, unique)
    alias: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)

    # Image information
    image: Mapped[str] = mapped_column(String(500), nullable=False)
    digest: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Container type
    persistent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # TTL for transient containers
    ttl_s: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Volume information
    volume_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Container status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running"
    )  # running, stopped, error

    def __repr__(self) -> str:
        """String representation of Container."""
        return (
            f"<Container(id={self.id}, alias={self.alias}, "
            f"image={self.image}, status={self.status})>"
        )
