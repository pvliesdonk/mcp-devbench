"""Exec model for tracking command executions in containers."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .base import Base


class Exec(Base):
    """Model for tracking command executions in containers."""

    __tablename__ = "execs"

    # Primary key - opaque ID in format "e_{uuid}"
    exec_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    # Foreign key to container
    container_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("containers.id"), nullable=False
    )

    # Command information
    cmd: Mapped[dict] = mapped_column(JSON, nullable=False)  # Command array as JSON
    as_root: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Timestamps
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Exit status
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Resource usage
    usage: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # {cpu_ms, mem_peak_mb, wall_ms}

    def __repr__(self) -> str:
        """String representation of Exec."""
        return (
            f"<Exec(exec_id={self.exec_id}, container_id={self.container_id}, "
            f"cmd={self.cmd}, exit_code={self.exit_code})>"
        )
