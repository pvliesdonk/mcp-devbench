"""Unit tests for WarmPoolManager."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from mcp_devbench.managers.warm_pool_manager import WarmPoolManager
from mcp_devbench.models.containers import Container


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock()
    settings.warm_pool_enabled = True
    settings.default_image_alias = "python:3.11-slim"
    settings.warm_health_check_interval = 60
    return settings


@pytest.fixture
def mock_container_manager():
    """Create mock container manager."""
    manager = AsyncMock()
    manager.docker_client = MagicMock()
    return manager


@pytest.fixture
def warm_pool_manager(mock_settings, mock_container_manager):
    """Create WarmPoolManager with mocked dependencies."""
    with patch("mcp_devbench.managers.warm_pool_manager.get_settings") as mock_get_settings:
        mock_get_settings.return_value = mock_settings
        manager = WarmPoolManager(mock_container_manager)
        yield manager


@pytest.fixture
def mock_container():
    """Create a mock container."""
    from datetime import datetime

    container = Container(
        id="c_123",
        docker_id="docker_123",
        alias=None,
        image="python:3.11-slim",
        persistent=False,
        created_at=datetime.now(),
        last_seen=datetime.now(),
        status="running",
    )
    return container


@pytest.mark.asyncio
async def test_start_disabled(mock_settings, mock_container_manager):
    """Test starting warm pool when disabled."""
    mock_settings.warm_pool_enabled = False

    with patch("mcp_devbench.managers.warm_pool_manager.get_settings") as mock_get_settings:
        mock_get_settings.return_value = mock_settings
        manager = WarmPoolManager(mock_container_manager)

        await manager.start()

        # Should not create any container
        mock_container_manager.create_container.assert_not_called()


@pytest.mark.asyncio
async def test_start_creates_warm_container(
    warm_pool_manager, mock_container_manager, mock_container
):
    """Test starting warm pool creates a container."""
    mock_container_manager.create_container.return_value = mock_container

    # Patch the health check loop to prevent it from running
    with patch.object(warm_pool_manager, "_health_check_loop", return_value=None):
        await warm_pool_manager.start()

    # Should create and start container
    mock_container_manager.create_container.assert_called_once()
    mock_container_manager.start_container.assert_called_once_with(mock_container.id)


@pytest.mark.asyncio
async def test_claim_warm_container_success(
    warm_pool_manager, mock_container_manager, mock_container
):
    """Test claiming a warm container successfully."""
    # Set up warm container
    warm_pool_manager._warm_container = mock_container

    # Mock the ensure_warm_container task
    with patch.object(warm_pool_manager, "_ensure_warm_container", return_value=None):
        claimed = await warm_pool_manager.claim_warm_container()

    assert claimed == mock_container
    assert warm_pool_manager._warm_container is None

    # Should start creating new warm container
    # Note: asyncio.create_task is called, so we can't easily assert on it


@pytest.mark.asyncio
async def test_claim_warm_container_none_available(warm_pool_manager):
    """Test claiming when no warm container available."""
    warm_pool_manager._warm_container = None

    claimed = await warm_pool_manager.claim_warm_container()

    assert claimed is None


@pytest.mark.asyncio
async def test_claim_warm_container_disabled(mock_settings, mock_container_manager):
    """Test claiming when warm pool is disabled."""
    mock_settings.warm_pool_enabled = False

    with patch("mcp_devbench.managers.warm_pool_manager.get_settings") as mock_get_settings:
        mock_get_settings.return_value = mock_settings
        manager = WarmPoolManager(mock_container_manager)

        claimed = await manager.claim_warm_container()

    assert claimed is None


@pytest.mark.asyncio
async def test_ensure_warm_container(warm_pool_manager, mock_container_manager, mock_container):
    """Test ensuring a warm container exists."""
    mock_container_manager.create_container.return_value = mock_container

    await warm_pool_manager._ensure_warm_container()

    assert warm_pool_manager._warm_container == mock_container
    mock_container_manager.create_container.assert_called_once()
    mock_container_manager.start_container.assert_called_once_with(mock_container.id)


@pytest.mark.asyncio
async def test_ensure_warm_container_already_exists(
    warm_pool_manager, mock_container_manager, mock_container
):
    """Test ensuring warm container when one already exists."""
    warm_pool_manager._warm_container = mock_container

    await warm_pool_manager._ensure_warm_container()

    # Should not create new container
    mock_container_manager.create_container.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_warm_container_failure(warm_pool_manager, mock_container_manager):
    """Test handling failure to create warm container."""
    mock_container_manager.create_container.side_effect = Exception("Creation failed")

    await warm_pool_manager._ensure_warm_container()

    assert warm_pool_manager._warm_container is None


@pytest.mark.asyncio
async def test_check_container_health_healthy(
    warm_pool_manager, mock_container_manager, mock_container
):
    """Test checking health of a healthy container."""
    # Mock Docker container
    mock_docker_container = MagicMock()
    mock_docker_container.status = "running"
    mock_docker_container.exec_run.return_value = MagicMock(exit_code=0)

    mock_container_manager.docker_client.containers.get.return_value = mock_docker_container

    is_healthy = await warm_pool_manager._check_container_health(mock_container)

    assert is_healthy is True


@pytest.mark.asyncio
async def test_check_container_health_not_running(
    warm_pool_manager, mock_container_manager, mock_container
):
    """Test checking health of a stopped container."""
    # Mock Docker container
    mock_docker_container = MagicMock()
    mock_docker_container.status = "exited"

    mock_container_manager.docker_client.containers.get.return_value = mock_docker_container

    is_healthy = await warm_pool_manager._check_container_health(mock_container)

    assert is_healthy is False


@pytest.mark.asyncio
async def test_check_container_health_exec_failed(
    warm_pool_manager, mock_container_manager, mock_container
):
    """Test checking health when exec fails."""
    # Mock Docker container
    mock_docker_container = MagicMock()
    mock_docker_container.status = "running"
    mock_docker_container.exec_run.return_value = MagicMock(exit_code=1)

    mock_container_manager.docker_client.containers.get.return_value = mock_docker_container

    is_healthy = await warm_pool_manager._check_container_health(mock_container)

    assert is_healthy is False


@pytest.mark.asyncio
async def test_check_container_health_not_found(
    warm_pool_manager, mock_container_manager, mock_container
):
    """Test checking health when container not found."""
    from docker.errors import NotFound

    mock_container_manager.docker_client.containers.get.side_effect = NotFound("not found")

    is_healthy = await warm_pool_manager._check_container_health(mock_container)

    assert is_healthy is False


@pytest.mark.asyncio
async def test_stop(warm_pool_manager):
    """Test stopping the warm pool manager."""
    warm_pool_manager._is_running = True

    # Create a real task that we can cancel
    async def dummy_task():
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            # Task cancellation is expected during this test; ignore the exception
            pass

    warm_pool_manager._health_check_task = asyncio.create_task(dummy_task())

    await warm_pool_manager.stop()

    assert warm_pool_manager._is_running is False
    assert warm_pool_manager._health_check_task.cancelled()


def test_get_warm_container_id(warm_pool_manager, mock_container):
    """Test getting warm container ID."""
    warm_pool_manager._warm_container = mock_container

    container_id = warm_pool_manager.get_warm_container_id()

    assert container_id == mock_container.id


def test_get_warm_container_id_none(warm_pool_manager):
    """Test getting warm container ID when none exists."""
    warm_pool_manager._warm_container = None

    container_id = warm_pool_manager.get_warm_container_id()

    assert container_id is None


@pytest.mark.asyncio
async def test_clean_workspace(warm_pool_manager, mock_container):
    """Test cleaning workspace."""
    # Mock ExecManager
    with patch("mcp_devbench.managers.exec_manager.ExecManager") as mock_exec_manager_class:
        mock_exec_manager = AsyncMock()
        mock_exec_manager.execute.return_value = "e_123"
        mock_exec_manager_class.return_value = mock_exec_manager

        await warm_pool_manager._clean_workspace(mock_container.id)

        mock_exec_manager.execute.assert_called_once()
        call_args = mock_exec_manager.execute.call_args
        assert call_args[1]["container_id"] == mock_container.id
        assert "rm -rf" in " ".join(call_args[1]["cmd"])


@pytest.mark.asyncio
async def test_clean_workspace_failure(warm_pool_manager, mock_container):
    """Test handling workspace cleanup failure."""
    # Mock ExecManager to fail
    with patch("mcp_devbench.managers.exec_manager.ExecManager") as mock_exec_manager_class:
        mock_exec_manager = AsyncMock()
        mock_exec_manager.execute.side_effect = Exception("Exec failed")
        mock_exec_manager_class.return_value = mock_exec_manager

        # Should not raise exception
        await warm_pool_manager._clean_workspace(mock_container.id)


@pytest.mark.asyncio
async def test_claim_with_alias(warm_pool_manager, mock_container_manager, mock_container):
    """Test claiming warm container with an alias."""
    warm_pool_manager._warm_container = mock_container

    # Mock database operations
    with patch("mcp_devbench.models.database.get_db_manager") as mock_db_manager:
        mock_session = AsyncMock()
        mock_db_manager.return_value.get_session.return_value.__aenter__.return_value = mock_session
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()

        # Mock ContainerRepository
        with patch("mcp_devbench.repositories.containers.ContainerRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get.return_value = mock_container
            mock_repo_class.return_value = mock_repo

            with patch.object(warm_pool_manager, "_ensure_warm_container", return_value=None):
                claimed = await warm_pool_manager.claim_warm_container(alias="my-container")

            assert claimed.id == mock_container.id
