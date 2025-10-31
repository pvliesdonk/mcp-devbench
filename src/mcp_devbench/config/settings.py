"""Settings and configuration management for MCP DevBench."""

from functools import lru_cache
from typing import List, Literal

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

    # Transport configuration
    transport_mode: Literal["stdio", "sse", "streamable-http"] = Field(
        default="streamable-http",
        description="Transport protocol for MCP server (stdio, sse, or streamable-http)",
    )

    path: str = Field(
        default="/mcp",
        description="Path for HTTP-based transports (sse or streamable-http)",
    )

    # Authentication configuration
    auth_mode: Literal["none", "bearer", "oauth", "oidc"] = Field(
        default="none",
        description="Authentication mode (none, bearer, oauth, or oidc)",
    )

    # Bearer token authentication
    bearer_token: str | None = Field(
        default=None,
        description="Bearer token for bearer authentication mode",
    )

    # OAuth/OIDC configuration
    oauth_client_id: str | None = Field(
        default=None,
        description="OAuth/OIDC client ID",
    )

    oauth_client_secret: str | None = Field(
        default=None,
        description="OAuth/OIDC client secret",
    )

    oauth_config_url: str | None = Field(
        default=None,
        description="OAuth provider configuration URL (for OIDC, this is the .well-known URL)",
    )

    oauth_base_url: str | None = Field(
        default=None,
        description="Base URL of this server for OAuth callbacks",
    )

    oauth_redirect_path: str = Field(
        default="/auth/callback",
        description="OAuth callback redirect path",
    )

    oauth_audience: str | None = Field(
        default=None,
        description="OAuth audience parameter (required by some providers like Auth0)",
    )

    oauth_required_scopes: str = Field(
        default="",
        description="Comma-separated list of required OAuth scopes",
    )

    @property
    def allowed_registries_list(self) -> List[str]:
        """Parse allowed registries into a list."""
        return [r.strip() for r in self.allowed_registries.split(",") if r.strip()]

    @property
    def oauth_required_scopes_list(self) -> List[str]:
        """Parse OAuth required scopes into a list."""
        if not self.oauth_required_scopes:
            return []
        return [s.strip() for s in self.oauth_required_scopes.split(",") if s.strip()]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
