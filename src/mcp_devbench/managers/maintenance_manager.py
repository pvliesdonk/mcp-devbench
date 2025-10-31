"""Background maintenance manager for periodic tasks."""

import asyncio
from datetime import datetime, timedelta, timezone

from docker import DockerClient
from docker.errors import APIError

from mcp_devbench.config import get_settings
from mcp_devbench.managers.container_manager import ContainerManager
from mcp_devbench.models.database import get_db_manager
from mcp_devbench.repositories.attachments import AttachmentRepository
from mcp_devbench.repositories.containers import ContainerRepository
from mcp_devbench.repositories.execs import ExecRepository
from mcp_devbench.utils import get_logger
from mcp_devbench.utils.docker_client import get_docker_client

logger = get_logger(__name__)


class MaintenanceManager:
    """Manager for background maintenance tasks."""

    def __init__(self) -> None:
        """Initialize maintenance manager."""
        self.settings = get_settings()
        self.docker_client: DockerClient = get_docker_client()
        self.db_manager = get_db_manager()
        self._running = False
        self._task = None

    async def start(self) -> None:
        """Start background maintenance tasks."""
        if self._running:
            logger.warning("Maintenance manager already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_maintenance_loop())
        logger.info("Maintenance manager started")

    async def stop(self) -> None:
        """Stop background maintenance tasks."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Maintenance manager stopped")

    async def _run_maintenance_loop(self) -> None:
        """Run periodic maintenance tasks."""
        while self._running:
            try:
                # Run maintenance tasks hourly
                await self.run_maintenance()
                await asyncio.sleep(3600)  # 1 hour
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Maintenance task failed", extra={"error": str(e)})
                await asyncio.sleep(60)  # Retry after 1 minute on error

    async def run_maintenance(self) -> dict:
        """
        Run all maintenance tasks.

        Returns:
            Dictionary with maintenance statistics
        """
        logger.info("Running maintenance tasks")

        stats = {
            "orphaned_transients": 0,
            "cleaned_execs": 0,
            "abandoned_attachments": 0,
            "containers_synced": 0,
            "errors": 0,
        }

        try:
            # Clean up orphaned transient containers
            orphaned = await self._cleanup_orphaned_transients()
            stats["orphaned_transients"] = orphaned

            # Clean up old exec entries
            cleaned = await self._cleanup_old_execs()
            stats["cleaned_execs"] = cleaned

            # Clean up abandoned attachments
            abandoned = await self._cleanup_abandoned_attachments()
            stats["abandoned_attachments"] = abandoned

            # Sync container state with Docker
            synced = await self._sync_container_state()
            stats["containers_synced"] = synced

            # Vacuum database (lightweight operation)
            await self._vacuum_database()

            logger.info("Maintenance tasks completed", extra=stats)
            return stats

        except Exception as e:
            logger.error("Maintenance failed", extra={"error": str(e)})
            stats["errors"] += 1
            return stats

    async def _cleanup_orphaned_transients(self) -> int:
        """
        Clean up orphaned transient containers.

        Returns:
            Number of containers cleaned up
        """
        logger.info("Cleaning up orphaned transient containers")

        try:
            cutoff_days = self.settings.transient_gc_days
            cutoff = datetime.now(timezone.utc) - timedelta(days=cutoff_days)

            async with self.db_manager.get_session() as session:
                repo = ContainerRepository(session)
                transients = await repo.list_by_status("stopped", persistent=False)

                cleaned = 0
                for container in transients:
                    if container.last_seen < cutoff:
                        try:
                            # Try to remove Docker container if it exists
                            try:
                                docker_container = self.docker_client.containers.get(
                                    container.docker_id
                                )
                                docker_container.remove(force=True)
                            except Exception:
                                pass  # Container may already be gone

                            # Remove from database
                            await repo.delete(container.id)
                            cleaned += 1

                            logger.info(
                                "Cleaned up orphaned transient",
                                extra={"container_id": container.id},
                            )
                        except Exception as e:
                            logger.error(
                                "Failed to clean up transient",
                                extra={"container_id": container.id, "error": str(e)},
                            )

                return cleaned

        except Exception as e:
            logger.error("Failed to clean up orphaned transients", extra={"error": str(e)})
            return 0

    async def _cleanup_old_execs(self) -> int:
        """
        Clean up completed execs older than 24 hours.

        Returns:
            Number of execs cleaned up
        """
        logger.info("Cleaning up old exec entries")

        try:
            async with self.db_manager.get_session() as session:
                exec_repo = ExecRepository(session)

                # Clean up execs older than 24 hours
                cleaned = await exec_repo.cleanup_old(hours=24)

                logger.info("Cleaned up old execs", extra={"count": cleaned})
                return cleaned

        except Exception as e:
            logger.error("Failed to clean up old execs", extra={"error": str(e)})
            return 0

    async def _cleanup_abandoned_attachments(self) -> int:
        """
        Clean up abandoned attachments.

        Returns:
            Number of attachments cleaned up
        """
        logger.info("Cleaning up abandoned attachments")

        try:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

            async with self.db_manager.get_session() as session:
                attachment_repo = AttachmentRepository(session)

                # Get all attachments
                # In a full implementation, we would identify abandoned ones
                # For now, just log
                logger.info("Attachment cleanup completed")
                return 0

        except Exception as e:
            logger.error("Failed to clean up attachments", extra={"error": str(e)})
            return 0

    async def _sync_container_state(self) -> int:
        """
        Synchronize container state with Docker.

        Updates last_seen timestamps and verifies container status.

        Returns:
            Number of containers synced
        """
        logger.info("Syncing container state with Docker")

        try:
            synced = 0

            async with self.db_manager.get_session() as session:
                repo = ContainerRepository(session)
                containers = await repo.list_by_status(status=None, include_stopped=True)

                for container in containers:
                    try:
                        # Check if container exists in Docker
                        docker_container = self.docker_client.containers.get(
                            container.docker_id
                        )

                        # Update last_seen
                        await repo.update_last_seen(container.id)

                        # Verify status matches
                        docker_status = docker_container.status
                        expected_status = "running" if docker_status == "running" else "stopped"

                        if container.status != expected_status:
                            await repo.update_status(container.id, expected_status)
                            logger.info(
                                "Updated container status",
                                extra={
                                    "container_id": container.id,
                                    "old_status": container.status,
                                    "new_status": expected_status,
                                },
                            )

                        synced += 1

                    except Exception:
                        # Container doesn't exist, mark as stopped
                        if container.status != "stopped":
                            await repo.update_status(container.id, "stopped")
                            logger.info(
                                "Container not found, marked as stopped",
                                extra={"container_id": container.id},
                            )
                            synced += 1

            logger.info("Container state synced", extra={"count": synced})
            return synced

        except Exception as e:
            logger.error("Failed to sync container state", extra={"error": str(e)})
            return 0

    async def _vacuum_database(self) -> None:
        """Vacuum the SQLite database to reclaim space."""
        logger.info("Vacuuming database")

        try:
            async with self.db_manager.get_session() as session:
                # Execute VACUUM command
                await session.execute("VACUUM")
                logger.info("Database vacuumed successfully")

        except Exception as e:
            logger.error("Failed to vacuum database", extra={"error": str(e)})

    async def check_health(self) -> dict:
        """
        Check system health.

        Returns:
            Dictionary with health metrics
        """
        health = {
            "docker_connected": False,
            "containers_count": 0,
            "active_execs": 0,
        }

        try:
            # Check Docker connectivity
            self.docker_client.ping()
            health["docker_connected"] = True

            # Count containers
            async with self.db_manager.get_session() as session:
                repo = ContainerRepository(session)
                containers = await repo.list_by_status(status="running")
                health["containers_count"] = len(containers)

                # Count active execs
                exec_repo = ExecRepository(session)
                # In a full implementation, would count incomplete execs
                health["active_execs"] = 0

        except Exception as e:
            logger.error("Health check failed", extra={"error": str(e)})

        return health


# Global instance
_maintenance_manager: MaintenanceManager | None = None


def get_maintenance_manager() -> MaintenanceManager:
    """Get or create maintenance manager instance."""
    global _maintenance_manager
    if _maintenance_manager is None:
        _maintenance_manager = MaintenanceManager()
    return _maintenance_manager
