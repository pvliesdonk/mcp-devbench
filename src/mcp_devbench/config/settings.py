"""Settings and configuration management for MCP DevBench."""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Registry configuration
    allowed_registries: str = Field(
        default="docker.io,ghcr.io",
        description="Comma-separated list of allowed Docker registries",
    )

    # State database configuration
    state_db: str = Field(
        default="./state.db",
        description="Path to SQLite state database",
    )

    # Container lifecycle configuration
    drain_grace_s: int = Field(
        default=60,
        description="Grace period in seconds for draining operations during shutdown",
    )

    transient_gc_days: int = Field(
        default=7,
        description="Days to keep transient containers before garbage collection",
    )

    # Docker configuration
    docker_host: str | None = Field(
        default=None,
        description="Docker daemon host URL (defaults to Docker's standard detection)",
    )

    # Logging configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    log_format: str = Field(
        default="json",
        description="Log format (json or text)",
    )

    # Server configuration
    host: str = Field(
        default="0.0.0.0",
        description="Server host to bind to",
    )

    port: int = Field(
        default=8000,
        description="Server port to bind to",
    )

    # Warm pool configuration
    default_image_alias: str = Field(
        default="python:3.11-slim",
        description="Default image for warm container pool",
    )

    warm_pool_enabled: bool = Field(
        default=True,
        description="Enable warm container pool for fast attach",
    )

    warm_health_check_interval: int = Field(
        default=60,
        description="Interval in seconds for warm container health checks",
    )

    @property
    def allowed_registries_list(self) -> List[str]:
        """Parse allowed registries into a list."""
        return [r.strip() for r in self.allowed_registries.split(",") if r.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
