"""Unit tests for ContainerRepository."""

from datetime import datetime
from uuid import uuid4

import pytest

from mcp_devbench.models.containers import Container
from mcp_devbench.repositories.containers import ContainerRepository


@pytest.mark.asyncio
async def test_create_container(db_session):
    """Test creating a container."""
    repo = ContainerRepository(db_session)

    container = Container(
        id=f"c_{uuid4()}",
        docker_id=f"docker_{uuid4()}",
        alias="test-container",
        image="python:3.11",
        persistent=False,
        created_at=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        status="running",
    )

    created = await repo.create(container)

    assert created.id == container.id
    assert created.alias == "test-container"
    assert created.status == "running"


@pytest.mark.asyncio
async def test_get_container_by_id(db_session):
    """Test getting a container by ID."""
    repo = ContainerRepository(db_session)

    container = Container(
        id=f"c_{uuid4()}",
        docker_id=f"docker_{uuid4()}",
        image="python:3.11",
        persistent=False,
        created_at=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        status="running",
    )

    await repo.create(container)

    retrieved = await repo.get(container.id)
    assert retrieved is not None
    assert retrieved.id == container.id


@pytest.mark.asyncio
async def test_get_container_by_alias(db_session):
    """Test getting a container by alias."""
    repo = ContainerRepository(db_session)

    container = Container(
        id=f"c_{uuid4()}",
        docker_id=f"docker_{uuid4()}",
        alias="my-alias",
        image="python:3.11",
        persistent=False,
        created_at=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        status="running",
    )

    await repo.create(container)

    retrieved = await repo.get_by_alias("my-alias")
    assert retrieved is not None
    assert retrieved.alias == "my-alias"


@pytest.mark.asyncio
async def test_get_container_by_identifier(db_session):
    """Test getting a container by ID or alias."""
    repo = ContainerRepository(db_session)

    container = Container(
        id=f"c_{uuid4()}",
        docker_id=f"docker_{uuid4()}",
        alias="my-alias",
        image="python:3.11",
        persistent=False,
        created_at=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        status="running",
    )

    await repo.create(container)

    # Test by ID
    retrieved = await repo.get_by_identifier(container.id)
    assert retrieved is not None
    assert retrieved.id == container.id

    # Test by alias
    retrieved = await repo.get_by_identifier("my-alias")
    assert retrieved is not None
    assert retrieved.alias == "my-alias"


@pytest.mark.asyncio
async def test_update_container_status(db_session):
    """Test updating container status."""
    repo = ContainerRepository(db_session)

    container = Container(
        id=f"c_{uuid4()}",
        docker_id=f"docker_{uuid4()}",
        image="python:3.11",
        persistent=False,
        created_at=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        status="running",
    )

    await repo.create(container)

    updated = await repo.update_status(container.id, "stopped")
    assert updated is not None
    assert updated.status == "stopped"


@pytest.mark.asyncio
async def test_list_containers_by_status(db_session):
    """Test listing containers by status."""
    repo = ContainerRepository(db_session)

    # Create running container
    container1 = Container(
        id=f"c_{uuid4()}",
        docker_id=f"docker_{uuid4()}",
        image="python:3.11",
        persistent=False,
        created_at=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        status="running",
    )
    await repo.create(container1)

    # Create stopped container
    container2 = Container(
        id=f"c_{uuid4()}",
        docker_id=f"docker_{uuid4()}",
        image="python:3.11",
        persistent=False,
        created_at=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        status="stopped",
    )
    await repo.create(container2)

    # List only running
    running = await repo.list_by_status(include_stopped=False)
    assert len(running) == 1
    assert running[0].status == "running"

    # List all
    all_containers = await repo.list_by_status(include_stopped=True)
    assert len(all_containers) == 2


@pytest.mark.asyncio
async def test_delete_container(db_session):
    """Test deleting a container."""
    repo = ContainerRepository(db_session)

    container = Container(
        id=f"c_{uuid4()}",
        docker_id=f"docker_{uuid4()}",
        image="python:3.11",
        persistent=False,
        created_at=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        status="running",
    )

    await repo.create(container)

    await repo.delete(container)
    await db_session.commit()  # Ensure deletion is committed

    retrieved = await repo.get(container.id)
    assert retrieved is None
