"""Tests for ReconciliationManager."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_devbench.managers.reconciliation_manager import ReconciliationManager
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
def reconciliation_manager(mock_docker_client, mock_db_manager):
    """Create ReconciliationManager with mocked dependencies."""
    manager = ReconciliationManager()
    manager.docker_client = mock_docker_client
    db_manager, session = mock_db_manager
    manager.db_manager = db_manager
    return manager, mock_docker_client, session


@pytest.mark.asyncio
async def test_reconcile_discovers_containers(reconciliation_manager):
    """Test that reconcile discovers containers with MCP label."""
    manager, docker_client, session = reconciliation_manager

    # Mock Docker containers
    mock_container = MagicMock()
    mock_container.id = "docker123"
    mock_container.labels = {
        "com.mcp.devbench": "true",
        "com.mcp.container_id": "c_test123",
    }
    mock_container.status = "running"
    mock_container.attrs = {"Mounts": []}
    mock_container.image.tags = ["python:3.11-slim"]

    docker_client.containers.list.return_value = [mock_container]

    # Mock empty database
    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "list_all", new_callable=AsyncMock) as mock_list:
        with patch.object(ContainerRepository, "create", new_callable=AsyncMock):
            mock_list.return_value = []

            stats = await manager.reconcile()

            assert stats["discovered"] == 1
            assert stats["adopted"] == 1


@pytest.mark.asyncio
async def test_reconcile_cleans_up_missing_containers(reconciliation_manager):
    """Test that reconcile cleans up containers missing from Docker."""
    manager, docker_client, session = reconciliation_manager

    # Mock no Docker containers
    docker_client.containers.list.return_value = []

    # Mock database container
    db_container = Container(
        id="c_test123",
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

    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "list_all", new_callable=AsyncMock) as mock_list:
        with patch.object(
            ContainerRepository, "update_status", new_callable=AsyncMock
        ) as mock_update:
            mock_list.return_value = [db_container]

            stats = await manager.reconcile()

            assert stats["cleaned_up"] == 1
            mock_update.assert_called_once()


@pytest.mark.asyncio
async def test_reconcile_handles_orphaned_transients(reconciliation_manager):
    """Test that reconcile removes old transient containers."""
    manager, docker_client, session = reconciliation_manager
    manager.settings.transient_gc_days = 7

    # Mock no Docker containers
    docker_client.containers.list.return_value = []

    # Mock old transient container
    old_date = datetime.now(timezone.utc) - timedelta(days=10)
    old_container = Container(
        id="c_old123",
        docker_id="dockerold123",
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

    from mcp_devbench.repositories.containers import ContainerRepository
    from docker.errors import NotFound

    with patch.object(ContainerRepository, "list_all", new_callable=AsyncMock) as mock_list:
        with patch.object(
            ContainerRepository, "list_by_status", new_callable=AsyncMock
        ) as mock_list_status:
            with patch.object(
                ContainerRepository, "delete", new_callable=AsyncMock
            ) as mock_delete:
                mock_list.return_value = []
                mock_list_status.return_value = [old_container]

                # Mock Docker container not found
                docker_client.containers.get.side_effect = NotFound("Not found")

                stats = await manager.reconcile()

                assert stats["orphaned"] == 1
                mock_delete.assert_called_once_with("c_old123")


@pytest.mark.asyncio
async def test_adopt_container_with_alias(reconciliation_manager):
    """Test adopting a container with an alias."""
    manager, docker_client, session = reconciliation_manager

    # Mock Docker container with alias
    mock_container = MagicMock()
    mock_container.id = "docker123"
    mock_container.labels = {
        "com.mcp.devbench": "true",
        "com.mcp.container_id": "c_test123",
        "com.mcp.alias": "my-container",
    }
    mock_container.status = "running"
    mock_container.attrs = {
        "Mounts": [{"Destination": "/workspace", "Name": "mcpdevbench_persist_c_test123"}]
    }
    mock_container.image.tags = ["python:3.11-slim"]

    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "create", new_callable=AsyncMock) as mock_create:
        await manager._adopt_container(mock_container, session)

        mock_create.assert_called_once()
        call_args = mock_create.call_args[0][0]
        assert call_args.id == "c_test123"
        assert call_args.alias == "my-container"
        assert call_args.persistent is True


@pytest.mark.asyncio
async def test_adopt_container_without_id_skips(reconciliation_manager):
    """Test that adopting a container without ID is skipped."""
    manager, docker_client, session = reconciliation_manager

    # Mock Docker container without container_id label
    mock_container = MagicMock()
    mock_container.id = "docker123"
    mock_container.labels = {"com.mcp.devbench": "true"}

    from mcp_devbench.repositories.containers import ContainerRepository

    with patch.object(ContainerRepository, "create", new_callable=AsyncMock) as mock_create:
        await manager._adopt_container(mock_container, session)

        # Should not create container
        mock_create.assert_not_called()


@pytest.mark.asyncio
async def test_discover_containers_returns_empty_on_error(reconciliation_manager):
    """Test that discovery returns empty list on error."""
    manager, docker_client, session = reconciliation_manager

    # Mock Docker API error
    from docker.errors import APIError

    docker_client.containers.list.side_effect = APIError("Connection failed")

    containers = manager._discover_containers()

    assert containers == []
