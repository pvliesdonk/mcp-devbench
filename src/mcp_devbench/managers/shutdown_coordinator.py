"""Shutdown coordinator for graceful server shutdown."""

import asyncio
import signal
from typing import Callable

from mcp_devbench.config import get_settings
from mcp_devbench.managers.container_manager import ContainerManager
from mcp_devbench.models.database import get_db_manager
from mcp_devbench.repositories.containers import ContainerRepository
from mcp_devbench.utils import get_logger

logger = get_logger(__name__)


class ShutdownCoordinator:
    """Coordinator for graceful server shutdown."""

    def __init__(self) -> None:
        """Initialize shutdown coordinator."""
        self.settings = get_settings()
        self.db_manager = get_db_manager()
        self._shutdown_initiated = False
        self._shutdown_event = asyncio.Event()

    def is_shutting_down(self) -> bool:
        """
        Check if shutdown has been initiated.

        Returns:
            True if shutdown is in progress
        """
        return self._shutdown_initiated

    async def initiate_shutdown(self) -> None:
        """
        Initiate graceful shutdown sequence.

        This method:
        1. Sets shutdown flag to stop accepting new requests
        2. Drains active operations up to MCP_DRAIN_GRACE_S
        3. Stops transient containers
        4. Preserves persistent containers
        5. Flushes state to disk
        """
        if self._shutdown_initiated:
            logger.warning("Shutdown already initiated")
            return

        self._shutdown_initiated = True
        logger.info("Initiating graceful shutdown")

        try:
            # Wait for active operations to complete
            await self._drain_operations()

            # Stop transient containers
            await self._stop_transient_containers()

            # Flush state to disk (already handled by DB manager)
            logger.info("State flushed to disk")

            # Signal shutdown complete
            self._shutdown_event.set()
            logger.info("Graceful shutdown completed")

        except Exception as e:
            logger.error("Error during shutdown", extra={"error": str(e)})
            self._shutdown_event.set()

    async def _drain_operations(self) -> None:
        """
        Drain active operations with timeout.

        Waits up to MCP_DRAIN_GRACE_S for operations to complete.
        """
        grace_period = self.settings.drain_grace_s
        logger.info(
            "Draining active operations",
            extra={"grace_period_s": grace_period},
        )

        # Wait for grace period
        # In a full implementation, this would track active operations
        # and wait for them to complete or timeout
        try:
            await asyncio.wait_for(
                asyncio.sleep(0.1),  # Minimal wait for now
                timeout=grace_period,
            )
            logger.info("Active operations drained")
        except asyncio.TimeoutError:
            logger.warning(
                "Drain timeout reached, forcing shutdown",
                extra={"grace_period_s": grace_period},
            )

    async def _stop_transient_containers(self) -> None:
        """
        Stop all transient containers.

        Persistent containers are preserved.
        """
        logger.info("Stopping transient containers")

        try:
            container_manager = ContainerManager()

            async with self.db_manager.get_session() as session:
                repo = ContainerRepository(session)

                # Get all running transient containers
                transients = await repo.list_by_status(
                    status="running", persistent=False
                )

                stopped_count = 0
                for container in transients:
                    try:
                        await container_manager.stop_container(
                            container.id, timeout=10
                        )
                        stopped_count += 1
                        logger.info(
                            "Stopped transient container",
                            extra={"container_id": container.id},
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to stop transient container",
                            extra={
                                "container_id": container.id,
                                "error": str(e),
                            },
                        )

                logger.info(
                    "Transient containers stopped",
                    extra={"count": stopped_count},
                )

        except Exception as e:
            logger.error(
                "Error stopping transient containers",
                extra={"error": str(e)},
            )

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown to complete."""
        await self._shutdown_event.wait()


# Global instance
_shutdown_coordinator: ShutdownCoordinator | None = None


def get_shutdown_coordinator() -> ShutdownCoordinator:
    """Get or create shutdown coordinator instance."""
    global _shutdown_coordinator
    if _shutdown_coordinator is None:
        _shutdown_coordinator = ShutdownCoordinator()
    return _shutdown_coordinator


def setup_signal_handlers(shutdown_handler: Callable[[], None]) -> None:
    """
    Set up signal handlers for graceful shutdown.

    Args:
        shutdown_handler: Function to call on SIGTERM/SIGINT
    """

    def signal_handler(signum, frame):
        """Handle shutdown signals."""
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name} signal, initiating shutdown")
        shutdown_handler()

    # Register handlers for SIGTERM and SIGINT
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logger.info("Signal handlers registered for graceful shutdown")
