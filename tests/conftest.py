"""Test configuration and fixtures."""

import asyncio
from typing import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from mcp_devbench.models.base import Base
from mcp_devbench.models.database import init_db
from mcp_devbench.utils.docker_client import get_docker_client


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db_engine():
    """Create test database engine."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async_session = sessionmaker(test_db_engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="session")
def docker_available():
    """Check if Docker daemon is available."""
    try:
        client = get_docker_client()
        client.ping()
        return True
    except Exception:
        return False


@pytest.fixture
def require_docker(docker_available):
    """Skip test if Docker is not available."""
    if not docker_available:
        pytest.skip("Docker daemon not available - skipping E2E test")


@pytest.fixture(scope="session", autouse=True)
async def setup_integration_env(docker_available):
    """Setup environment for integration tests."""
    # Initialize database for all tests
    await init_db()

    # Only pull images if Docker is available
    if docker_available:
        docker_client = get_docker_client()
        try:
            docker_client.images.pull("alpine:latest")
            docker_client.images.pull("python:3.11-slim")
        except Exception:
            pass  # Images might already exist

    yield

    # Cleanup
    # (Database cleanup happens automatically for in-memory DB)
