"""Tests for spawn idempotency (QW-5)."""

import pytest
from datetime import datetime, timedelta, timezone

from mcp_devbench.managers.container_manager import ContainerManager
from mcp_devbench.models.containers import Container
from mcp_devbench.models.database import get_db_manager
from mcp_devbench.repositories.containers import ContainerRepository


@pytest.mark.asyncio
async def test_spawn_with_idempotency_key_prevents_duplicates():
    """Test that spawning with same idempotency key returns existing container."""
    manager = ContainerManager()
    idempotency_key = "test-key-123"

    # First spawn - should create new container
    container1 = await manager.create_container(
        image="alpine:latest",
        idempotency_key=idempotency_key,
    )

    assert container1.idempotency_key == idempotency_key
    assert container1.idempotency_key_created_at is not None

    # Second spawn with same key - should return existing container
    container2 = await manager.create_container(
        image="alpine:latest",
        idempotency_key=idempotency_key,
    )

    assert container1.id == container2.id
    assert container2.idempotency_key == idempotency_key

    # Cleanup
    await manager.remove_container(container1.id, force=True)


@pytest.mark.asyncio
async def test_spawn_without_idempotency_key_creates_new_containers():
    """Test that spawning without idempotency key creates separate containers."""
    manager = ContainerManager()

    # First spawn
    container1 = await manager.create_container(image="alpine:latest")
    assert container1.idempotency_key is None

    # Second spawn
    container2 = await manager.create_container(image="alpine:latest")
    assert container2.idempotency_key is None

    # Should be different containers
    assert container1.id != container2.id

    # Cleanup
    await manager.remove_container(container1.id, force=True)
    await manager.remove_container(container2.id, force=True)


@pytest.mark.asyncio
async def test_idempotency_key_expires_after_24_hours():
    """Test that idempotency keys expire after 24 hours."""
    manager = ContainerManager()
    db_manager = get_db_manager()
    idempotency_key = "test-key-expired"

    # Create container with idempotency key
    container1 = await manager.create_container(
        image="alpine:latest",
        idempotency_key=idempotency_key,
    )

    # Manually set created_at to 25 hours ago to make the key expired
    async with db_manager.get_session() as session:
        repo = ContainerRepository(session)
        container = await repo.get(container1.id)
        old_timestamp = datetime.now(timezone.utc) - timedelta(hours=25)
        container.idempotency_key_created_at = old_timestamp
        await session.commit()

    # Try to create another container with the same key
    # It should NOT return the existing container because the key is expired
    # Instead, it should try to create a new one (which will fail due to unique constraint)
    # This test verifies that expired keys are not considered valid
    try:
        container2 = await manager.create_container(
            image="alpine:latest",
            idempotency_key=idempotency_key,
        )
        # If we get here, it means a new container was created or the old one was returned
        # We expect it to try creating a new one, which would fail due to unique constraint
        # But if the implementation is checking expiry correctly, it won't return the old container
        assert container2.id != container1.id, "Should not return expired container"
    except Exception as e:
        # Expected: unique constraint failure because we're trying to create a new container
        # with the same idempotency key that still exists in DB
        assert "UNIQUE constraint failed" in str(e) or "IntegrityError" in str(e.__class__.__name__)

    # Cleanup
    await manager.remove_container(container1.id, force=True)


@pytest.mark.asyncio
async def test_different_idempotency_keys_create_different_containers():
    """Test that different idempotency keys create separate containers."""
    manager = ContainerManager()

    # Create with first key
    container1 = await manager.create_container(
        image="alpine:latest",
        idempotency_key="key-1",
    )

    # Create with second key
    container2 = await manager.create_container(
        image="alpine:latest",
        idempotency_key="key-2",
    )

    # Should be different containers
    assert container1.id != container2.id
    assert container1.idempotency_key == "key-1"
    assert container2.idempotency_key == "key-2"

    # Cleanup
    await manager.remove_container(container1.id, force=True)
    await manager.remove_container(container2.id, force=True)


@pytest.mark.asyncio
async def test_get_by_idempotency_key_repository_method():
    """Test ContainerRepository.get_by_idempotency_key method."""
    manager = ContainerManager()
    db_manager = get_db_manager()
    idempotency_key = "test-repo-key"

    # Create container
    container = await manager.create_container(
        image="alpine:latest",
        idempotency_key=idempotency_key,
    )

    # Query by idempotency key
    async with db_manager.get_session() as session:
        repo = ContainerRepository(session)
        found = await repo.get_by_idempotency_key(idempotency_key)

        assert found is not None
        assert found.id == container.id
        assert found.idempotency_key == idempotency_key

    # Test non-existent key
    async with db_manager.get_session() as session:
        repo = ContainerRepository(session)
        not_found = await repo.get_by_idempotency_key("non-existent-key")
        assert not_found is None

    # Cleanup
    await manager.remove_container(container.id, force=True)
