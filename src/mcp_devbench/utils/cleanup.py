"""Shared cleanup utilities for container management."""

from datetime import datetime, timedelta, timezone

from docker import DockerClient
from docker.errors import NotFound

from mcp_devbench.repositories.containers import ContainerRepository
from mcp_devbench.utils import get_logger

logger = get_logger(__name__)


async def cleanup_orphaned_transients(
    docker_client: DockerClient,
    repo: ContainerRepository,
    transient_gc_days: int,
) -> int:
    """
    Clean up orphaned transient containers based on age.

    This is a shared utility function used by both ReconciliationManager
    and MaintenanceManager to avoid code duplication.

    Args:
        docker_client: Docker client instance
        repo: Container repository instance
        transient_gc_days: Days to keep transient containers before cleanup

    Returns:
        Number of containers cleaned up
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=transient_gc_days)
    transients = await repo.list_by_status("stopped", persistent=False)

    cleaned = 0
    for container in transients:
        if container.last_seen < cutoff:
            try:
                # Try to remove Docker container if it exists
                try:
                    docker_container = docker_client.containers.get(container.docker_id)
                    docker_container.remove(force=True)
                    logger.info(
                        "Removed orphaned Docker container",
                        extra={
                            "container_id": container.id,
                            "docker_id": container.docker_id,
                        },
                    )
                except NotFound:
                    # Container already removed from Docker
                    pass

                # Remove from database
                await repo.delete(container.id)
                cleaned += 1

                logger.info(
                    "Cleaned up orphaned transient container",
                    extra={
                        "container_id": container.id,
                        "age_days": (datetime.now(timezone.utc) - container.last_seen).days,
                    },
                )
            except Exception as e:
                logger.error(
                    "Failed to clean up orphaned container",
                    extra={"container_id": container.id, "error": str(e)},
                )

    return cleaned
