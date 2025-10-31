"""Tests for ShutdownCoordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_devbench.managers.shutdown_coordinator import ShutdownCoordinator
from mcp_devbench.models.containers import Container


@pytest.fixture
def mock_db_manager():
    """Create mock database manager."""
    manager = MagicMock()
    session = AsyncMock()
    manager.get_session.return_value.__aenter__.return_value = session
    return manager, session


@pytest.fixture
def shutdown_coordinator(mock_db_manager):
    """Create ShutdownCoordinator with mocked dependencies."""
    coordinator = ShutdownCoordinator()
    db_manager, session = mock_db_manager
    coordinator.db_manager = db_manager
    return coordinator, session


@pytest.mark.asyncio
async def test_shutdown_sets_flag(shutdown_coordinator):
    """Test that shutdown sets the shutdown flag."""
    coordinator, session = shutdown_coordinator

    assert not coordinator.is_shutting_down()

    # Mock container manager
    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "list_by_status", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []

        await coordinator.initiate_shutdown()

        assert coordinator.is_shutting_down()


@pytest.mark.asyncio
async def test_shutdown_stops_transient_containers(shutdown_coordinator):
    """Test that shutdown stops transient containers."""
    coordinator, session = shutdown_coordinator

    # Create mock transient container
    from datetime import datetime, timezone

    transient = Container(
        id="c_transient",
        docker_id="docker123",
        alias=None,
        image="python:3.11-slim",
        digest=None,
        persistent=False,
        created_at=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        ttl_s=None,
        volume_name=None,
        status="running",
    )

    from mcp_devbench.managers.container_manager import ContainerManager
    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "list_by_status", new_callable=AsyncMock) as mock_list:
        with patch.object(
            ContainerManager, "stop_container", new_callable=AsyncMock
        ) as mock_stop:
            mock_list.return_value = [transient]

            await coordinator.initiate_shutdown()

            mock_stop.assert_called_once_with("c_transient", timeout=10)


@pytest.mark.asyncio
async def test_shutdown_preserves_persistent_containers(shutdown_coordinator):
    """Test that shutdown does not stop persistent containers."""
    coordinator, session = shutdown_coordinator

    # Create mock persistent container
    from datetime import datetime, timezone

    persistent = Container(
        id="c_persistent",
        docker_id="docker456",
        alias="my-container",
        image="python:3.11-slim",
        digest=None,
        persistent=True,
        created_at=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        ttl_s=None,
        volume_name="mcpdevbench_persist_c_persistent",
        status="running",
    )

    from mcp_devbench.managers.container_manager import ContainerManager
    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "list_by_status", new_callable=AsyncMock) as mock_list:
        with patch.object(
            ContainerManager, "stop_container", new_callable=AsyncMock
        ) as mock_stop:
            # Only return transient containers (not persistent)
            mock_list.return_value = []

            await coordinator.initiate_shutdown()

            # Should not stop any containers
            mock_stop.assert_not_called()


@pytest.mark.asyncio
async def test_shutdown_idempotent(shutdown_coordinator):
    """Test that shutdown can be called multiple times safely."""
    coordinator, session = shutdown_coordinator

    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "list_by_status", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = []

        await coordinator.initiate_shutdown()
        await coordinator.initiate_shutdown()  # Second call should be no-op

        # Should only list containers once
        assert mock_list.call_count == 1


@pytest.mark.asyncio
async def test_shutdown_continues_on_error(shutdown_coordinator):
    """Test that shutdown continues even if stopping a container fails."""
    coordinator, session = shutdown_coordinator

    # Create mock transient containers
    from datetime import datetime, timezone

    transient1 = Container(
        id="c_transient1",
        docker_id="docker123",
        alias=None,
        image="python:3.11-slim",
        digest=None,
        persistent=False,
        created_at=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        ttl_s=None,
        volume_name=None,
        status="running",
    )

    transient2 = Container(
        id="c_transient2",
        docker_id="docker456",
        alias=None,
        image="python:3.11-slim",
        digest=None,
        persistent=False,
        created_at=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
        ttl_s=None,
        volume_name=None,
        status="running",
    )

    from mcp_devbench.managers.container_manager import ContainerManager
    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "list_by_status", new_callable=AsyncMock) as mock_list:
        with patch.object(
            ContainerManager, "stop_container", new_callable=AsyncMock
        ) as mock_stop:
            mock_list.return_value = [transient1, transient2]

            # First stop fails, second succeeds
            mock_stop.side_effect = [Exception("Stop failed"), None]

            await coordinator.initiate_shutdown()

            # Should have tried to stop both containers
            assert mock_stop.call_count == 2


@pytest.mark.asyncio
async def test_wait_for_shutdown(shutdown_coordinator):
    """Test waiting for shutdown to complete."""
    coordinator, session = shutdown_coordinator

    import asyncio

    from mcp_devbench.repositories.containers import ContainerRepository

    async def shutdown_later():
        await asyncio.sleep(0.1)
        with patch.object(
            ContainerRepository, "list_by_status", new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = []
            await coordinator.initiate_shutdown()

    # Start shutdown in background
    shutdown_task = asyncio.create_task(shutdown_later())

    # Wait for it to complete
    await coordinator.wait_for_shutdown()

    # Ensure shutdown task completed
    await shutdown_task
    assert coordinator.is_shutting_down()
