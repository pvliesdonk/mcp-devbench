"""MCP DevBench server implementation using FastMCP 2."""

import sys
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from pydantic import BaseModel

from mcp_devbench.config import get_settings
from mcp_devbench.models.database import close_db, init_db
from mcp_devbench.utils import get_logger, setup_logging
from mcp_devbench.utils.docker_client import close_docker_client, get_docker_client


class HealthCheckResponse(BaseModel):
    """Health check response model."""

    status: str
    docker_connected: bool
    database_initialized: bool = True
    version: str = "0.1.0"


# Initialize FastMCP server
mcp = FastMCP("MCP DevBench")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan():
    """Lifespan context manager for startup and shutdown tasks."""
    settings = get_settings()

    # Setup logging
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger.info("Starting MCP DevBench server", extra={"version": "0.1.0"})

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", extra={"error": str(e)})
        raise

    # Initialize Docker client
    try:
        docker_client = get_docker_client()
        logger.info("Docker client initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize Docker client", extra={"error": str(e)})
        raise

    yield

    # Cleanup
    logger.info("Shutting down MCP DevBench server")
    await close_db()
    close_docker_client()
    logger.info("MCP DevBench server stopped")


# Set lifespan
mcp.lifespan_handler = lifespan


@mcp.tool()
async def health() -> HealthCheckResponse:
    """
    Health check endpoint to verify server status and Docker connectivity.
    
    Returns:
        HealthCheckResponse with status and Docker connection info
    """
    try:
        docker_client = get_docker_client()
        docker_client.ping()
        docker_connected = True
    except Exception as e:
        logger.warning("Docker health check failed", extra={"error": str(e)})
        docker_connected = False

    return HealthCheckResponse(
        status="healthy" if docker_connected else "degraded",
        docker_connected=docker_connected,
        database_initialized=True,
    )


def main() -> None:
    """Main entry point for the MCP DevBench server."""
    settings = get_settings()

    logger.info(
        "Starting server",
        extra={
            "host": settings.host,
            "port": settings.port,
            "allowed_registries": settings.allowed_registries_list,
        },
    )

    try:
        # Run the FastMCP server
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        sys.exit(0)
    except Exception as e:
        logger.error("Server error", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()
