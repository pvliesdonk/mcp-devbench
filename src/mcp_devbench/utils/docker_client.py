"""Docker client utilities for MCP DevBench."""

import docker
from docker import DockerClient
from docker.errors import DockerException

from mcp_devbench.config import get_settings
from mcp_devbench.utils import get_logger

logger = get_logger(__name__)


class DockerClientManager:
    """Manages Docker client connection with connection pooling."""

    def __init__(self) -> None:
        """Initialize Docker client manager."""
        self._client: DockerClient | None = None
        self.settings = get_settings()

    def get_client(self) -> DockerClient:
        """
        Get or create Docker client instance.

        Returns:
            DockerClient instance

        Raises:
            DockerException: If unable to connect to Docker daemon
        """
        if self._client is None:
            try:
                if self.settings.docker_host:
                    self._client = docker.DockerClient(base_url=self.settings.docker_host)
                else:
                    self._client = docker.from_env()

                # Test connection
                self._client.ping()
                logger.info(
                    "Successfully connected to Docker daemon",
                    extra={"docker_version": self._client.version()},
                )
            except DockerException as e:
                logger.error("Failed to connect to Docker daemon", extra={"error": str(e)})
                raise

        return self._client

    def close(self) -> None:
        """Close Docker client connection."""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Docker client connection closed")


# Global instance
_docker_manager: DockerClientManager | None = None


def get_docker_client() -> DockerClient:
    """
    Get global Docker client instance.

    Returns:
        DockerClient instance
    """
    global _docker_manager
    if _docker_manager is None:
        _docker_manager = DockerClientManager()
    return _docker_manager.get_client()


def close_docker_client() -> None:
    """Close global Docker client connection."""
    global _docker_manager
    if _docker_manager:
        _docker_manager.close()
        _docker_manager = None
