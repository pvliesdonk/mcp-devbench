"""Unit tests for ExecManager."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from mcp_devbench.managers.exec_manager import ExecManager, ExecResult
from mcp_devbench.models.execs import Exec
from mcp_devbench.repositories.execs import ExecRepository
from mcp_devbench.utils.exceptions import ContainerNotFoundError, ExecNotFoundError


@pytest.fixture
def mock_docker_client():
    """Create mock Docker client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_container():
    """Create mock container."""
    container = MagicMock()
    container.id = "c_test123"
    container.docker_id = "docker123"
    return container


@pytest.fixture
def mock_exec_entry():
    """Create mock exec entry."""
    exec_entry = Exec(
        exec_id="e_test123",
        container_id="c_test123",
        cmd={"cmd": ["echo", "test"], "cwd": "/workspace", "env": {}},
        as_root=False,
        started_at=datetime.utcnow(),
    )
    return exec_entry


@pytest.mark.asyncio
async def test_execute_creates_exec_entry(db_session, mock_container):
    """Test that execute creates an exec entry in the database."""
    with patch("mcp_devbench.managers.exec_manager.get_docker_client") as mock_docker, \
         patch("mcp_devbench.managers.exec_manager.get_db_manager") as mock_db_mgr:
        
        # Setup mocks
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_db_mgr.return_value.get_session = MagicMock(return_value=mock_session_cm)
        
        # Create container in database
        from mcp_devbench.models.containers import Container
        from mcp_devbench.repositories.containers import ContainerRepository
        
        container = Container(
            id="c_test123",
            docker_id="docker123",
            image="alpine:latest",
            persistent=False,
            created_at=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            status="running",
        )
        container_repo = ContainerRepository(db_session)
        await container_repo.create(container)
        
        # Create ExecManager
        manager = ExecManager()
        
        # Execute command
        exec_id = await manager.execute(
            container_id="c_test123",
            cmd=["echo", "test"],
        )
        
        # Verify exec was created
        assert exec_id.startswith("e_")
        
        # Verify in database
        exec_repo = ExecRepository(db_session)
        exec_entry = await exec_repo.get(exec_id)
        assert exec_entry is not None
        assert exec_entry.container_id == "c_test123"
        assert exec_entry.cmd["cmd"] == ["echo", "test"]
        assert exec_entry.as_root is False


@pytest.mark.asyncio
async def test_execute_with_nonexistent_container(db_session):
    """Test that execute raises error for nonexistent container."""
    with patch("mcp_devbench.managers.exec_manager.get_docker_client") as mock_docker, \
         patch("mcp_devbench.managers.exec_manager.get_db_manager") as mock_db_mgr:
        
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_db_mgr.return_value.get_session = MagicMock(return_value=mock_session_cm)
        
        manager = ExecManager()
        
        with pytest.raises(ContainerNotFoundError) as exc_info:
            await manager.execute(
                container_id="c_nonexistent",
                cmd=["echo", "test"],
            )
        
        assert exc_info.value.identifier == "c_nonexistent"


@pytest.mark.asyncio
async def test_execute_with_as_root(db_session):
    """Test execute with as_root flag."""
    with patch("mcp_devbench.managers.exec_manager.get_docker_client") as mock_docker, \
         patch("mcp_devbench.managers.exec_manager.get_db_manager") as mock_db_mgr:
        
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_db_mgr.return_value.get_session = MagicMock(return_value=mock_session_cm)
        
        # Create container
        from mcp_devbench.models.containers import Container
        from mcp_devbench.repositories.containers import ContainerRepository
        
        container = Container(
            id="c_test123",
            docker_id="docker123",
            image="alpine:latest",
            persistent=False,
            created_at=datetime.utcnow(),
            last_seen=datetime.utcnow(),
            status="running",
        )
        container_repo = ContainerRepository(db_session)
        await container_repo.create(container)
        
        manager = ExecManager()
        
        exec_id = await manager.execute(
            container_id="c_test123",
            cmd=["whoami"],
            as_root=True,
        )
        
        # Verify as_root is stored
        exec_repo = ExecRepository(db_session)
        exec_entry = await exec_repo.get(exec_id)
        assert exec_entry.as_root is True


@pytest.mark.asyncio
async def test_get_exec_result(db_session):
    """Test getting exec result."""
    with patch("mcp_devbench.managers.exec_manager.get_docker_client") as mock_docker, \
         patch("mcp_devbench.managers.exec_manager.get_db_manager") as mock_db_mgr:
        
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_db_mgr.return_value.get_session = MagicMock(return_value=mock_session_cm)
        
        # Create exec entry
        exec_entry = Exec(
            exec_id="e_test123",
            container_id="c_test123",
            cmd={"cmd": ["echo", "test"], "cwd": "/workspace", "env": {}},
            as_root=False,
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            exit_code=0,
            usage={"wall_ms": 100},
        )
        exec_repo = ExecRepository(db_session)
        await exec_repo.create(exec_entry)
        
        manager = ExecManager()
        result = await manager.get_exec_result("e_test123")
        
        assert result.exec_id == "e_test123"
        assert result.exit_code == 0
        assert result.is_complete is True
        assert result.usage["wall_ms"] == 100


@pytest.mark.asyncio
async def test_get_exec_result_not_found(db_session):
    """Test getting result for nonexistent exec."""
    with patch("mcp_devbench.managers.exec_manager.get_docker_client") as mock_docker, \
         patch("mcp_devbench.managers.exec_manager.get_db_manager") as mock_db_mgr:
        
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_db_mgr.return_value.get_session = MagicMock(return_value=mock_session_cm)
        
        manager = ExecManager()
        
        with pytest.raises(ExecNotFoundError) as exc_info:
            await manager.get_exec_result("e_nonexistent")
        
        assert exc_info.value.exec_id == "e_nonexistent"


@pytest.mark.asyncio
async def test_get_active_execs(db_session):
    """Test getting active execs for a container."""
    with patch("mcp_devbench.managers.exec_manager.get_docker_client") as mock_docker, \
         patch("mcp_devbench.managers.exec_manager.get_db_manager") as mock_db_mgr:
        
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_db_mgr.return_value.get_session = MagicMock(return_value=mock_session_cm)
        
        exec_repo = ExecRepository(db_session)
        
        # Create active exec
        active_exec = Exec(
            exec_id="e_active",
            container_id="c_test123",
            cmd={"cmd": ["sleep", "10"], "cwd": "/workspace", "env": {}},
            as_root=False,
            started_at=datetime.utcnow(),
        )
        await exec_repo.create(active_exec)
        
        # Create completed exec
        completed_exec = Exec(
            exec_id="e_completed",
            container_id="c_test123",
            cmd={"cmd": ["echo", "done"], "cwd": "/workspace", "env": {}},
            as_root=False,
            started_at=datetime.utcnow(),
            ended_at=datetime.utcnow(),
            exit_code=0,
        )
        await exec_repo.create(completed_exec)
        
        manager = ExecManager()
        active_execs = await manager.get_active_execs("c_test123")
        
        assert len(active_execs) == 1
        assert active_execs[0].exec_id == "e_active"


@pytest.mark.asyncio
async def test_cleanup_old_execs(db_session):
    """Test cleaning up old completed execs."""
    with patch("mcp_devbench.managers.exec_manager.get_docker_client") as mock_docker, \
         patch("mcp_devbench.managers.exec_manager.get_db_manager") as mock_db_mgr:
        
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)
        mock_db_mgr.return_value.get_session = MagicMock(return_value=mock_session_cm)
        
        exec_repo = ExecRepository(db_session)
        
        # Create old completed exec
        from datetime import timedelta
        old_time = datetime.utcnow() - timedelta(hours=25)
        old_exec = Exec(
            exec_id="e_old",
            container_id="c_test123",
            cmd={"cmd": ["echo", "old"], "cwd": "/workspace", "env": {}},
            as_root=False,
            started_at=old_time,
            ended_at=old_time,
            exit_code=0,
        )
        await exec_repo.create(old_exec)
        
        manager = ExecManager()
        count = await manager.cleanup_old_execs(hours=24)
        
        assert count == 1
        
        # Verify exec was deleted
        result = await exec_repo.get("e_old")
        assert result is None


@pytest.mark.asyncio
async def test_semaphore_limits_concurrent_execs():
    """Test that semaphore limits concurrent executions per container."""
    with patch("mcp_devbench.managers.exec_manager.get_docker_client") as mock_docker:
        manager = ExecManager()
        
        # Get semaphore for a container
        sem1 = manager._get_container_semaphore("c_test1")
        sem2 = manager._get_container_semaphore("c_test1")
        sem3 = manager._get_container_semaphore("c_test2")
        
        # Same container should return same semaphore
        assert sem1 is sem2
        
        # Different container should return different semaphore
        assert sem1 is not sem3
        
        # Check initial value
        assert sem1._value == ExecManager.MAX_CONCURRENT_EXECS
