"""Tests for MaintenanceManager."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_devbench.managers.maintenance_manager import MaintenanceManager
from mcp_devbench.models.containers import Container


@pytest.fixture
def mock_docker_client():
    """Create mock Docker client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_db_manager():
    """Create mock database manager."""
    manager = MagicMock()
    session = AsyncMock()
    manager.get_session.return_value.__aenter__.return_value = session
    return manager, session


@pytest.fixture
def maintenance_manager(mock_docker_client, mock_db_manager):
    """Create MaintenanceManager with mocked dependencies."""
    manager = MaintenanceManager()
    manager.docker_client = mock_docker_client
    db_manager, session = mock_db_manager
    manager.db_manager = db_manager
    return manager, mock_docker_client, session


@pytest.mark.asyncio
async def test_cleanup_orphaned_transients(maintenance_manager):
    """Test cleanup of old transient containers."""
    manager, docker_client, session = maintenance_manager
    manager.settings.transient_gc_days = 7

    # Create old transient container
    old_date = datetime.now(timezone.utc) - timedelta(days=10)
    old_container = Container(
        id="c_old",
        docker_id="docker_old",
        alias=None,
        image="python:3.11-slim",
        digest=None,
        persistent=False,
        created_at=old_date,
        last_seen=old_date,
        ttl_s=None,
        volume_name=None,
        status="stopped",
    )

    from docker.errors import NotFound

    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "list_by_status", new_callable=AsyncMock) as mock_list:
        with patch.object(ContainerRepository, "delete", new_callable=AsyncMock):
            mock_list.return_value = [old_container]
            docker_client.containers.get.side_effect = NotFound("Not found")

            cleaned = await manager._cleanup_orphaned_transients()

            assert cleaned == 1


@pytest.mark.asyncio
async def test_cleanup_old_execs(maintenance_manager):
    """Test cleanup of old exec entries."""
    manager, docker_client, session = maintenance_manager

    from mcp_devbench.repositories.execs import ExecRepository

    with patch.object(ExecRepository, "cleanup_old", new_callable=AsyncMock) as mock_cleanup:
        mock_cleanup.return_value = 5

        cleaned = await manager._cleanup_old_execs()

        assert cleaned == 5
        mock_cleanup.assert_called_once_with(hours=24)


@pytest.mark.asyncio
async def test_sync_container_state_updates_status(maintenance_manager):
    """Test syncing container state updates status."""
    manager, docker_client, session = maintenance_manager

    # Create container with mismatched status
    container = Container(
        id="c_test",
        docker_id="docker_test",
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

    # Mock Docker container as stopped
    mock_docker_container = MagicMock()
    mock_docker_container.status = "exited"
    docker_client.containers.get.return_value = mock_docker_container

    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "list_by_status", new_callable=AsyncMock) as mock_list:
        with patch.object(ContainerRepository, "update_last_seen", new_callable=AsyncMock):
            with patch.object(
                ContainerRepository, "update_status", new_callable=AsyncMock
            ) as mock_update:
                mock_list.return_value = [container]

                synced = await manager._sync_container_state()

                assert synced == 1
                mock_update.assert_called_once_with("c_test", "stopped")


@pytest.mark.asyncio
async def test_sync_container_state_marks_missing_stopped(maintenance_manager):
    """Test syncing marks missing containers as stopped."""
    manager, docker_client, session = maintenance_manager

    # Create container
    container = Container(
        id="c_test",
        docker_id="docker_test",
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

    # Mock Docker container not found
    from docker.errors import NotFound

    docker_client.containers.get.side_effect = NotFound("Not found")

    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "list_by_status", new_callable=AsyncMock) as mock_list:
        with patch.object(
            ContainerRepository, "update_status", new_callable=AsyncMock
        ) as mock_update:
            mock_list.return_value = [container]

            synced = await manager._sync_container_state()

            assert synced == 1
            mock_update.assert_called_once_with("c_test", "stopped")


@pytest.mark.asyncio
async def test_check_health_returns_metrics(maintenance_manager):
    """Test health check returns metrics."""
    manager, docker_client, session = maintenance_manager

    # Mock Docker ping
    docker_client.ping.return_value = True

    # Mock running containers
    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "list_by_status", new_callable=AsyncMock) as mock_list:
        mock_list.return_value = [MagicMock(), MagicMock()]

        health = await manager.check_health()

        assert health["docker_connected"] is True
        assert health["containers_count"] == 2


@pytest.mark.asyncio
async def test_check_health_handles_docker_error(maintenance_manager):
    """Test health check handles Docker errors."""
    manager, docker_client, session = maintenance_manager

    # Mock Docker error
    from docker.errors import APIError

    docker_client.ping.side_effect = APIError("Connection failed")

    health = await manager.check_health()

    assert health["docker_connected"] is False


@pytest.mark.asyncio
async def test_run_maintenance_returns_stats(maintenance_manager):
    """Test run_maintenance returns statistics."""
    manager, docker_client, session = maintenance_manager

    from mcp_devbench.repositories.containers import ContainerRepository
    from mcp_devbench.repositories.execs import ExecRepository

    with patch.object(ContainerRepository, "list_by_status", new_callable=AsyncMock) as mock_list:
        with patch.object(ExecRepository, "cleanup_old", new_callable=AsyncMock) as mock_cleanup:
            with patch.object(session, "execute", new_callable=AsyncMock):
                mock_list.return_value = []
                mock_cleanup.return_value = 3

                stats = await manager.run_maintenance()

                assert "orphaned_transients" in stats
                assert "cleaned_execs" in stats
                assert stats["cleaned_execs"] == 3


@pytest.mark.asyncio
async def test_start_and_stop_maintenance(maintenance_manager):
    """Test starting and stopping maintenance tasks."""
    manager, docker_client, session = maintenance_manager

    # Start maintenance
    await manager.start()
    assert manager._running is True

    # Stop maintenance
    await manager.stop()
    assert manager._running is False
