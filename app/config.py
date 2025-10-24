"""config.py — ENV-first configuration for MCP Devbench (M0).

This module centralizes all environment variables and documents their purpose.
Transport defaults: HTTP (streamable) via FastMCP2; STDIO as fallback."""
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Comprehensive settings parsed from environment (with `.env` support).

    Key decisions for M0:
    - HTTP transport is the default; use STDIO fallback if MCP_TRANSPORT=stdio.
    - Default container alias is `default`.
    - Image pull policy defaults to `if-missing`.
    """

    # Runtime / container
    default_image: str = Field(default="ubuntu:24.04", alias="DEFAULT_IMAGE")
    default_alias: str = Field(default="default", alias="DEFAULT_CONTAINER_ALIAS")
    default_image_pull: str = Field(default="if-missing", alias="DEFAULT_IMAGE_PULL")
    workspace_root: str = Field(default="/workspace", alias="WORKSPACE_ROOT")
    sqlite_path: str = Field(default="./state.db", alias="SQLITE_PATH")
    docker_host: str = Field(default="unix:///var/run/docker.sock", alias="DOCKER_HOST")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # MCP transport
    mcp_name: str = Field(default="mcp-devbench", alias="MCP_NAME")
    mcp_transport: str = Field(default="http", alias="MCP_TRANSPORT")  # http|stdio
    mcp_http_host: str = Field(default="0.0.0.0", alias="MCP_HTTP_HOST")
    mcp_http_port: int = Field(default=8765, alias="MCP_HTTP_PORT")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
