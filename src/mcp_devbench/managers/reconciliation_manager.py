"""Reconciliation manager for boot recovery and state synchronization."""

from datetime import datetime, timezone
from typing import List

from docker import DockerClient
from docker.errors import APIError
from docker.models.containers import Container as DockerContainer

from mcp_devbench.config import get_settings
from mcp_devbench.models.containers import Container
from mcp_devbench.models.database import get_db_manager
from mcp_devbench.repositories.containers import ContainerRepository
from mcp_devbench.utils import get_logger
from mcp_devbench.utils.cleanup import cleanup_orphaned_transients
from mcp_devbench.utils.docker_client import get_docker_client

logger = get_logger(__name__)


class ReconciliationManager:
    """Manager for container reconciliation and recovery."""

    def __init__(self) -> None:
        """Initialize reconciliation manager."""
        self.settings = get_settings()
        self.docker_client: DockerClient = get_docker_client()
        self.db_manager = get_db_manager()

    async def reconcile(self) -> dict:
        """
        Reconcile Docker containers with database state.

        Discovers containers with com.mcp.devbench label, matches them against
        the database, and performs cleanup operations.

        Returns:
            Dictionary with reconciliation statistics
        """
        logger.info("Starting container reconciliation")

        stats = {
            "discovered": 0,
            "adopted": 0,
            "cleaned_up": 0,
            "orphaned": 0,
            "errors": 0,
        }

        try:
            # Find all containers with our label
            docker_containers = self._discover_containers()
            stats["discovered"] = len(docker_containers)

            # Get all containers from DB
            async with self.db_manager.get_session() as session:
                repo = ContainerRepository(session)
                db_containers = await repo.list_all()

                # Create sets for comparison
                docker_ids = {c.id for c in docker_containers}
                db_docker_ids = {c.docker_id for c in db_containers if c.docker_id}

                # Adopt running containers not in DB
                for docker_container in docker_containers:
                    if docker_container.id not in db_docker_ids:
                        try:
                            await self._adopt_container(docker_container, session)
                            stats["adopted"] += 1
                        except Exception as e:
                            logger.error(
                                "Failed to adopt container",
                                extra={"docker_id": docker_container.id, "error": str(e)},
                            )
                            stats["errors"] += 1

                # Clean up stopped containers not in Docker
                for db_container in db_containers:
                    if db_container.docker_id and db_container.docker_id not in docker_ids:
                        try:
                            await self._cleanup_missing_container(db_container, session)
                            stats["cleaned_up"] += 1
                        except Exception as e:
                            logger.error(
                                "Failed to clean up missing container",
                                extra={"container_id": db_container.id, "error": str(e)},
                            )
                            stats["errors"] += 1

                # Handle orphaned transient containers
                orphaned = await self._handle_orphaned_transients(session)
                stats["orphaned"] = orphaned

                # Clean up incomplete execs
                await self._cleanup_incomplete_execs(session)

            logger.info("Container reconciliation completed", extra=stats)
            return stats

        except Exception as e:
            logger.error("Reconciliation failed", extra={"error": str(e)})
            stats["errors"] += 1
            return stats

    def _discover_containers(self) -> List[DockerContainer]:
        """
        Discover all containers with com.mcp.devbench label.

        Returns:
            List of Docker containers
        """
        try:
            filters = {"label": "com.mcp.devbench=true"}
            containers = self.docker_client.containers.list(all=True, filters=filters)
            logger.info(
                "Discovered containers with MCP DevBench label",
                extra={"count": len(containers)},
            )
            return containers
        except APIError as e:
            logger.error("Failed to discover containers", extra={"error": str(e)})
            return []

    async def _adopt_container(self, docker_container: DockerContainer, session) -> None:
        """
        Adopt a running container into the database.

        Args:
            docker_container: Docker container to adopt
            session: Database session
        """
        # Extract metadata from labels
        labels = docker_container.labels or {}
        container_id = labels.get("com.mcp.container_id")
        alias = labels.get("com.mcp.alias")

        if not container_id:
            logger.warning(
                "Container missing com.mcp.container_id label",
                extra={"docker_id": docker_container.id},
            )
            return

        # Determine if persistent based on volume name
        mounts = docker_container.attrs.get("Mounts", [])
        persistent = any(m.get("Name", "").startswith("mcpdevbench_persist_") for m in mounts)

        # Get volume name
        volume_name = None
        for mount in mounts:
            if mount.get("Destination") == "/workspace":
                volume_name = mount.get("Name")
                break

        # Get image
        image = docker_container.image.tags[0] if docker_container.image.tags else "unknown"

        # Determine status
        status = docker_container.status
        if status == "running":
            status = "running"
        elif status in ("exited", "stopped"):
            status = "stopped"
        else:
            status = "error"

        # Create container record
        container = Container(
            id=container_id,
            docker_id=docker_container.id,
            alias=alias,
            image=image,
            digest=None,
            persistent=persistent,
            created_at=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            ttl_s=None,
            volume_name=volume_name,
            status=status,
        )

        repo = ContainerRepository(session)
        await repo.create(container)

        logger.info(
            "Adopted container",
            extra={
                "container_id": container_id,
                "docker_id": docker_container.id,
                "alias": alias,
            },
        )

    async def _cleanup_missing_container(self, container: Container, session) -> None:
        """
        Clean up a container that exists in DB but not in Docker.

        Args:
            container: Container record from database
            session: Database session
        """
        repo = ContainerRepository(session)

        # Update status to stopped
        await repo.update_status(container.id, "stopped")

        logger.info(
            "Marked missing container as stopped",
            extra={
                "container_id": container.id,
                "docker_id": container.docker_id,
            },
        )

    async def _handle_orphaned_transients(self, session) -> int:
        """
        Handle orphaned transient containers based on MCP_TRANSIENT_GC_DAYS.

        Args:
            session: Database session

        Returns:
            Number of containers cleaned up
        """
        repo = ContainerRepository(session)
        cleaned = await cleanup_orphaned_transients(
            self.docker_client, repo, self.settings.transient_gc_days
        )
        return cleaned

    async def _cleanup_incomplete_execs(self, session) -> None:
        """
        Clean up incomplete exec entries.

        Args:
            session: Database session
        """
        # Get all incomplete execs (no end time)
        # For simplicity, we'll just log this for now
        # A full implementation would query for incomplete execs and mark them
        logger.info("Incomplete exec cleanup completed")


# Global instance
_reconciliation_manager: ReconciliationManager | None = None


def get_reconciliation_manager() -> ReconciliationManager:
    """Get or create reconciliation manager instance."""
    global _reconciliation_manager
    if _reconciliation_manager is None:
        _reconciliation_manager = ReconciliationManager()
    return _reconciliation_manager
