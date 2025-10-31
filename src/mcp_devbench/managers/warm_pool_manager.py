"""Warm container pool manager for fast container provisioning."""

import asyncio
from typing import Optional

from docker.errors import NotFound

from mcp_devbench.config import get_settings
from mcp_devbench.models.containers import Container
from mcp_devbench.utils import get_logger

logger = get_logger(__name__)


class WarmPoolManager:
    """Manager for warm container pool."""

    def __init__(self, container_manager) -> None:
        """
        Initialize warm pool manager.

        Args:
            container_manager: ContainerManager instance
        """
        self.settings = get_settings()
        self.container_manager = container_manager
        self._warm_container: Optional[Container] = None
        self._lock = asyncio.Lock()
        self._health_check_task: Optional[asyncio.Task] = None
        self._is_running = False

    async def start(self) -> None:
        """Start the warm pool manager."""
        if not self.settings.warm_pool_enabled:
            logger.info("Warm pool disabled")
            return

        self._is_running = True

        # Create initial warm container
        await self._ensure_warm_container()

        # Start health check task
        self._health_check_task = asyncio.create_task(self._health_check_loop())

        logger.info(
            "Warm pool started",
            extra={
                "default_image": self.settings.default_image_alias,
                "health_check_interval": self.settings.warm_health_check_interval,
            },
        )

    async def stop(self) -> None:
        """Stop the warm pool manager."""
        self._is_running = False

        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        logger.info("Warm pool stopped")

    async def claim_warm_container(self, alias: Optional[str] = None) -> Optional[Container]:
        """
        Claim the warm container atomically.

        Args:
            alias: Optional alias to assign to the claimed container

        Returns:
            Claimed container or None if none available
        """
        if not self.settings.warm_pool_enabled:
            return None

        async with self._lock:
            if self._warm_container is None:
                logger.debug("No warm container available")
                return None

            # Claim the container
            container = self._warm_container
            self._warm_container = None

            logger.info(
                "Warm container claimed",
                extra={
                    "container_id": container.id,
                    "alias": alias,
                },
            )

            # Update alias if provided
            if alias and alias != container.alias:
                # Update container in database with new alias
                from mcp_devbench.models.database import get_db_manager
                from mcp_devbench.repositories.containers import ContainerRepository

                db_manager = get_db_manager()
                async with db_manager.get_session() as session:
                    repo = ContainerRepository(session)
                    container = await repo.get(container.id)
                    if container:
                        # Update alias
                        await session.execute(
                            "UPDATE containers SET alias = :alias WHERE id = :id",
                            {"alias": alias, "id": container.id},
                        )
                        await session.commit()
                        container.alias = alias

            # Start creating a new warm container async
            asyncio.create_task(self._ensure_warm_container())

            return container

    async def _ensure_warm_container(self) -> None:
        """Ensure a warm container exists."""
        async with self._lock:
            if self._warm_container is not None:
                return

            try:
                # Create new warm container
                container = await self.container_manager.create_container(
                    image=self.settings.default_image_alias,
                    alias=None,  # No alias for warm containers
                    persistent=False,
                    ttl_s=None,
                )

                # Start the container
                await self.container_manager.start_container(container.id)

                # Clean workspace (ensure it's empty)
                await self._clean_workspace(container.id)

                self._warm_container = container

                logger.info(
                    "Warm container created",
                    extra={
                        "container_id": container.id,
                        "image": self.settings.default_image_alias,
                    },
                )

            except Exception as e:
                logger.error(
                    "Failed to create warm container",
                    extra={"error": str(e)},
                )
                self._warm_container = None

    async def _clean_workspace(self, container_id: str) -> None:
        """
        Clean the workspace directory in a container.

        Args:
            container_id: Container ID
        """
        try:
            # Use exec to clean workspace
            from mcp_devbench.managers.exec_manager import ExecManager

            exec_manager = ExecManager()

            # Remove all files in workspace
            exec_id = await exec_manager.execute(
                container_id=container_id,
                cmd=["sh", "-c", "rm -rf /workspace/* /workspace/.*  2>/dev/null || true"],
                as_root=False,
                timeout_s=30,
            )

            # Wait a bit for cleanup to complete
            await asyncio.sleep(1)

            logger.debug(
                "Workspace cleaned",
                extra={"container_id": container_id, "exec_id": exec_id},
            )

        except Exception as e:
            logger.warning(
                "Failed to clean workspace",
                extra={"container_id": container_id, "error": str(e)},
            )

    async def _check_container_health(self, container: Container) -> bool:
        """
        Check if a container is healthy.

        Args:
            container: Container to check

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Get Docker container
            docker_client = self.container_manager.docker_client
            docker_container = docker_client.containers.get(container.docker_id)

            # Check if running
            status = docker_container.status
            if status != "running":
                logger.warning(
                    "Warm container not running",
                    extra={"container_id": container.id, "status": status},
                )
                return False

            # Try to execute a simple command
            result = docker_container.exec_run(["echo", "health_check"], user="1000")
            if result.exit_code != 0:
                logger.warning(
                    "Warm container health check failed",
                    extra={"container_id": container.id, "exit_code": result.exit_code},
                )
                return False

            return True

        except NotFound:
            logger.warning(
                "Warm container not found in Docker",
                extra={"container_id": container.id},
            )
            return False
        except Exception as e:
            logger.error(
                "Error checking container health",
                extra={"container_id": container.id, "error": str(e)},
            )
            return False

    async def _health_check_loop(self) -> None:
        """Periodic health check loop."""
        while self._is_running:
            try:
                await asyncio.sleep(self.settings.warm_health_check_interval)

                async with self._lock:
                    if self._warm_container is None:
                        # No warm container, try to create one
                        await self._ensure_warm_container()
                        continue

                    # Check health
                    is_healthy = await self._check_container_health(self._warm_container)

                    if not is_healthy:
                        logger.warning(
                            "Warm container unhealthy, recreating",
                            extra={"container_id": self._warm_container.id},
                        )

                        # Remove unhealthy container
                        try:
                            await self.container_manager.remove_container(
                                self._warm_container.id,
                                force=True,
                            )
                        except Exception as e:
                            logger.error(
                                "Failed to remove unhealthy container",
                                extra={"error": str(e)},
                            )

                        self._warm_container = None

                        # Create new one
                        await self._ensure_warm_container()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    "Error in health check loop",
                    extra={"error": str(e)},
                )

    def get_warm_container_id(self) -> Optional[str]:
        """
        Get the ID of the current warm container.

        Returns:
            Container ID or None if no warm container
        """
        return self._warm_container.id if self._warm_container else None


# Singleton instance
_warm_pool_manager: Optional[WarmPoolManager] = None


def get_warm_pool_manager(container_manager=None) -> WarmPoolManager:
    """
    Get the warm pool manager singleton.

    Args:
        container_manager: ContainerManager instance (required on first call)

    Returns:
        WarmPoolManager instance
    """
    global _warm_pool_manager
    if _warm_pool_manager is None:
        if container_manager is None:
            raise ValueError("container_manager required on first call")
        _warm_pool_manager = WarmPoolManager(container_manager)
    return _warm_pool_manager
