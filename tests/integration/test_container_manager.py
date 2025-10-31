"""Integration tests for ContainerManager with real Docker."""

import pytest

from mcp_devbench.managers.container_manager import ContainerManager
from mcp_devbench.utils.exceptions import (
    ContainerAlreadyExistsError,
    ContainerNotFoundError,
)


@pytest.mark.asyncio
async def test_create_and_start_container():
    """Test creating and starting a container."""
    manager = ContainerManager()

    # Create container
    container = await manager.create_container(
        image="alpine:latest", alias="test-alpine", persistent=False
    )

    assert container.id.startswith("c_")
    assert container.alias == "test-alpine"
    assert container.status == "stopped"

    try:
        # Start container
        await manager.start_container(container.id)

        # Get container to verify status
        updated = await manager.get_container(container.id)
        assert updated.status == "running"

    finally:
        # Cleanup
        try:
            await manager.stop_container(container.id)
            await manager.remove_container(container.id)
        except Exception:
            pass  # Ignore cleanup errors in test teardown


@pytest.mark.asyncio
async def test_create_container_with_duplicate_alias():
    """Test that creating a container with duplicate alias fails."""
    manager = ContainerManager()

    # Create first container
    container1 = await manager.create_container(
        image="alpine:latest", alias="duplicate-test", persistent=False
    )

    try:
        # Try to create second container with same alias
        with pytest.raises(ContainerAlreadyExistsError):
            await manager.create_container(
                image="alpine:latest", alias="duplicate-test", persistent=False
            )

    finally:
        # Cleanup
        try:
            await manager.remove_container(container1.id, force=True)
        except Exception:
            pass  # Ignore cleanup errors in test teardown


@pytest.mark.asyncio
async def test_stop_and_remove_container():
    """Test stopping and removing a container."""
    manager = ContainerManager()

    # Create and start container
    container = await manager.create_container(image="alpine:latest", persistent=False)
    await manager.start_container(container.id)

    # Stop container
    await manager.stop_container(container.id)

    # Verify stopped
    updated = await manager.get_container(container.id)
    assert updated.status == "stopped"

    # Remove container
    await manager.remove_container(container.id)

    # Verify removed
    with pytest.raises(ContainerNotFoundError):
        await manager.get_container(container.id)


@pytest.mark.asyncio
async def test_get_container_by_id_and_alias():
    """Test getting container by ID and alias."""
    manager = ContainerManager()

    # Create container
    container = await manager.create_container(
        image="alpine:latest", alias="get-test", persistent=False
    )

    try:
        # Get by ID
        by_id = await manager.get_container(container.id)
        assert by_id.id == container.id

        # Get by alias
        by_alias = await manager.get_container("get-test")
        assert by_alias.id == container.id
        assert by_alias.alias == "get-test"

    finally:
        # Cleanup
        try:
            await manager.remove_container(container.id, force=True)
        except Exception:
            pass  # Ignore cleanup errors in test teardown


@pytest.mark.asyncio
async def test_list_containers():
    """Test listing containers."""
    manager = ContainerManager()

    # Create running container
    container1 = await manager.create_container(
        image="alpine:latest", alias="list-test-1", persistent=False
    )
    await manager.start_container(container1.id)

    # Create stopped container
    container2 = await manager.create_container(
        image="alpine:latest", alias="list-test-2", persistent=False
    )

    try:
        # List only running
        running = await manager.list_containers(include_stopped=False)
        running_ids = [c.id for c in running]
        assert container1.id in running_ids
        assert container2.id not in running_ids

        # List all
        all_containers = await manager.list_containers(include_stopped=True)
        all_ids = [c.id for c in all_containers]
        assert container1.id in all_ids
        assert container2.id in all_ids

    finally:
        # Cleanup
        try:
            await manager.remove_container(container1.id, force=True)
            await manager.remove_container(container2.id, force=True)
        except Exception:
            pass  # Ignore cleanup errors in test teardown


@pytest.mark.asyncio
async def test_container_not_found_errors():
    """Test that operations on non-existent containers raise appropriate errors."""
    manager = ContainerManager()

    # Test get
    with pytest.raises(ContainerNotFoundError):
        await manager.get_container("nonexistent")

    # Test start
    with pytest.raises(ContainerNotFoundError):
        await manager.start_container("nonexistent")

    # Test stop
    with pytest.raises(ContainerNotFoundError):
        await manager.stop_container("nonexistent")

    # Test remove
    with pytest.raises(ContainerNotFoundError):
        await manager.remove_container("nonexistent")
