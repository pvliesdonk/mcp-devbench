"""Unit tests for MCP tool endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_devbench.mcp_tools import (
    AttachInput,
    CancelInput,
    ExecInput,
    ExecPollInput,
    FileDeleteInput,
    FileListInput,
    FileReadInput,
    FileStatInput,
    FileWriteInput,
    KillInput,
    SpawnInput,
)
from mcp_devbench.models.containers import Container
from mcp_devbench.utils.exceptions import ContainerNotFoundError


@pytest.mark.asyncio
async def test_spawn_tool():
    """Test spawn tool endpoint."""
    from mcp_devbench import server

    # Import the actual function, not the decorated one

    with patch("mcp_devbench.server.ContainerManager") as mock_manager_class:
        mock_manager = AsyncMock()
        mock_manager_class.return_value = mock_manager

        # Mock container
        mock_container = Container(
            id="c_test123",
            docker_id="docker_abc123",
            alias="test-env",
            image="python:3.11",
            persistent=True,
            created_at=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            status="running",
        )

        mock_manager.create_container = AsyncMock(return_value=mock_container)
        mock_manager.start_container = AsyncMock()

        # Test spawn - call the function from the tool
        input_data = SpawnInput(
            image="python:3.11",
            persistent=True,
            alias="test-env",
        )

        result = await server.spawn.fn(input_data)

        assert result.container_id == "c_test123"
        assert result.alias == "test-env"
        assert result.status == "running"

        mock_manager.create_container.assert_called_once_with(
            image="python:3.11",
            alias="test-env",
            persistent=True,
            ttl_s=None,
        )
        mock_manager.start_container.assert_called_once_with("c_test123")


@pytest.mark.asyncio
async def test_attach_tool():
    """Test attach tool endpoint."""
    from mcp_devbench import server

    with patch("mcp_devbench.server.get_db_manager") as mock_db_mgr:
        mock_session = AsyncMock()
        mock_db_mgr.return_value.get_session = MagicMock()
        mock_db_mgr.return_value.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        mock_db_mgr.return_value.get_session.return_value.__aexit__ = AsyncMock()

        # Mock container
        mock_container = Container(
            id="c_test123",
            docker_id="docker_abc123",
            alias="test-env",
            image="python:3.11",
            persistent=True,
            created_at=datetime.now(timezone.utc),
            last_seen=datetime.now(timezone.utc),
            status="running",
        )

        with patch("mcp_devbench.server.ContainerRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_by_identifier = AsyncMock(return_value=mock_container)

            with patch("mcp_devbench.server.AttachmentRepository") as mock_attach_repo_class:
                mock_attach_repo = AsyncMock()
                mock_attach_repo_class.return_value = mock_attach_repo
                mock_attach_repo.create = AsyncMock()

                # Test attach
                input_data = AttachInput(
                    target="test-env",
                    client_name="test-client",
                    session_id="session-123",
                )

                result = await server.attach.fn(input_data)

                assert result.container_id == "c_test123"
                assert result.alias == "test-env"
                assert result.roots == ["workspace:c_test123"]

                mock_repo.get_by_identifier.assert_called_once_with("test-env")
                mock_attach_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_attach_tool_container_not_found():
    """Test attach tool with non-existent container."""
    from mcp_devbench import server

    with patch("mcp_devbench.server.get_db_manager") as mock_db_mgr:
        mock_session = AsyncMock()
        mock_db_mgr.return_value.get_session = MagicMock()
        mock_db_mgr.return_value.get_session.return_value.__aenter__ = AsyncMock(
            return_value=mock_session
        )
        # __aexit__ should accept exception info and return None (or False) to propagate exceptions
        mock_db_mgr.return_value.get_session.return_value.__aexit__ = AsyncMock(
            return_value=None
        )

        with patch("mcp_devbench.server.ContainerRepository") as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo_class.return_value = mock_repo
            mock_repo.get_by_identifier = AsyncMock(return_value=None)

            input_data = AttachInput(
                target="nonexistent",
                client_name="test-client",
                session_id="session-123",
            )

            with pytest.raises(ContainerNotFoundError):
                await server.attach.fn(input_data)


@pytest.mark.asyncio
async def test_kill_tool():
    """Test kill tool endpoint."""
    from mcp_devbench import server

    with patch("mcp_devbench.server.ContainerManager") as mock_manager_class:
        mock_manager = AsyncMock()
        mock_manager_class.return_value = mock_manager
        mock_manager.stop_container = AsyncMock()
        mock_manager.remove_container = AsyncMock()

        with patch("mcp_devbench.server.get_db_manager") as mock_db_mgr:
            mock_session = AsyncMock()
            mock_db_mgr.return_value.get_session = MagicMock()
            mock_db_mgr.return_value.get_session.return_value.__aenter__ = AsyncMock(
                return_value=mock_session
            )
            mock_db_mgr.return_value.get_session.return_value.__aexit__ = AsyncMock()

            with patch("mcp_devbench.server.AttachmentRepository") as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo_class.return_value = mock_repo
                mock_repo.detach_all_for_container = AsyncMock(return_value=2)

                # Test kill
                input_data = KillInput(container_id="c_test123", force=False)

                result = await server.kill.fn(input_data)

                assert result.status == "stopped"

                mock_manager.stop_container.assert_called_once_with("c_test123", timeout=10)
                mock_manager.remove_container.assert_called_once_with("c_test123", force=False)
                mock_repo.detach_all_for_container.assert_called_once_with("c_test123")


@pytest.mark.asyncio
async def test_exec_start_tool():
    """Test exec_start tool endpoint."""
    from mcp_devbench import server

    with patch("mcp_devbench.server.ExecManager") as mock_manager_class:
        mock_manager = AsyncMock()
        mock_manager_class.return_value = mock_manager
        mock_manager.execute = AsyncMock(return_value="e_exec123")

        # Test exec_start
        input_data = ExecInput(
            container_id="c_test123",
            cmd=["python", "script.py"],
            cwd="/workspace",
            env={"DEBUG": "1"},
            as_root=False,
            timeout_s=300,
        )

        result = await server.exec_start.fn(input_data)

        assert result.exec_id == "e_exec123"
        assert result.status == "running"

        mock_manager.execute.assert_called_once_with(
            container_id="c_test123",
            cmd=["python", "script.py"],
            cwd="/workspace",
            env={"DEBUG": "1"},
            as_root=False,
            timeout_s=300,
            idempotency_key=None,
        )


@pytest.mark.asyncio
async def test_exec_cancel_tool():
    """Test exec_cancel tool endpoint."""
    from mcp_devbench import server

    with patch("mcp_devbench.server.ExecManager") as mock_manager_class:
        mock_manager = AsyncMock()
        mock_manager_class.return_value = mock_manager
        mock_manager.cancel = AsyncMock()

        # Test exec_cancel
        input_data = CancelInput(exec_id="e_exec123")

        result = await server.exec_cancel.fn(input_data)

        assert result.status == "cancelled"
        assert result.exec_id == "e_exec123"

        mock_manager.cancel.assert_called_once_with("e_exec123")


@pytest.mark.asyncio
async def test_exec_poll_tool():
    """Test exec_poll tool endpoint."""
    from mcp_devbench import server

    with patch("mcp_devbench.server.get_output_streamer") as mock_streamer_fn:
        mock_streamer = AsyncMock()
        mock_streamer_fn.return_value = mock_streamer
        # Mock the poll method which returns (messages_list, is_complete)
        mock_streamer.poll = AsyncMock(
            return_value=(
                [
                    {
                        "seq": 1,
                        "stream": "stdout",
                        "data": "test output",
                        "ts": "2025-10-31T12:00:00",
                    },
                    {
                        "seq": 2,
                        "exit_code": 0,
                        "usage": {"wall_ms": 100},
                        "ts": "2025-10-31T12:00:01",
                        "complete": True,
                    },
                ],
                True,  # is_complete
            )
        )

        # Test exec_poll
        input_data = ExecPollInput(exec_id="e_exec123", after_seq=0)

        result = await server.exec_poll.fn(input_data)

        assert result.complete is True
        assert len(result.messages) == 2  # 1 output message + 1 completion message
        assert result.messages[0].stream == "stdout"
        assert result.messages[0].data == "test output"
        assert result.messages[1].exit_code == 0
        assert result.messages[1].complete is True

        # Verify poll was called correctly
        mock_streamer.poll.assert_called_once_with("e_exec123", after_seq=0)


@pytest.mark.asyncio
async def test_fs_read_tool():
    """Test fs_read tool endpoint."""
    from mcp_devbench import server

    with patch("mcp_devbench.server.FilesystemManager") as mock_manager_class:
        mock_manager = AsyncMock()
        mock_manager_class.return_value = mock_manager

        # Mock file content and info
        mock_content = b"test file content"

        from mcp_devbench.managers.filesystem_manager import FileInfo

        mock_file_info = FileInfo(
            path="/workspace/test.txt",
            size=17,
            is_dir=False,
            permissions="rw-r--r--",
            mtime=datetime.now(timezone.utc),
            etag="abc123",
            mime_type="text/plain",
        )
        # Mock read to return tuple of (content, file_info)
        mock_manager.read = AsyncMock(return_value=(mock_content, mock_file_info))

        # Test fs_read
        input_data = FileReadInput(container_id="c_test123", path="/workspace/test.txt")

        result = await server.fs_read.fn(input_data)

        assert result.content == mock_content
        assert result.etag == "abc123"
        assert result.size == 17
        assert result.mime_type == "text/plain"


@pytest.mark.asyncio
async def test_fs_write_tool():
    """Test fs_write tool endpoint."""
    from mcp_devbench import server

    with patch("mcp_devbench.server.FilesystemManager") as mock_manager_class:
        mock_manager = AsyncMock()
        mock_manager_class.return_value = mock_manager

        # Mock write and stat
        mock_manager.write = AsyncMock(return_value="new_etag123")

        from mcp_devbench.managers.filesystem_manager import FileInfo

        mock_file_info = FileInfo(
            path="/workspace/test.txt",
            size=17,
            is_dir=False,
            permissions="rw-r--r--",
            mtime=datetime.now(timezone.utc),
            etag="new_etag123",
        )
        mock_manager.stat = AsyncMock(return_value=mock_file_info)

        # Test fs_write
        input_data = FileWriteInput(
            container_id="c_test123",
            path="/workspace/test.txt",
            content=b"test content",
            if_match_etag="old_etag",
        )

        result = await server.fs_write.fn(input_data)

        assert result.path == "/workspace/test.txt"
        assert result.etag == "new_etag123"
        assert result.size == 17

        mock_manager.write.assert_called_once_with(
            "c_test123", "/workspace/test.txt", b"test content", if_match_etag="old_etag"
        )


@pytest.mark.asyncio
async def test_fs_delete_tool():
    """Test fs_delete tool endpoint."""
    from mcp_devbench import server

    with patch("mcp_devbench.server.FilesystemManager") as mock_manager_class:
        mock_manager = AsyncMock()
        mock_manager_class.return_value = mock_manager
        mock_manager.delete = AsyncMock()

        # Test fs_delete
        input_data = FileDeleteInput(container_id="c_test123", path="/workspace/test.txt")

        result = await server.fs_delete.fn(input_data)

        assert result.status == "deleted"
        assert result.path == "/workspace/test.txt"

        mock_manager.delete.assert_called_once_with("c_test123", "/workspace/test.txt")


@pytest.mark.asyncio
async def test_fs_stat_tool():
    """Test fs_stat tool endpoint."""
    from mcp_devbench import server

    with patch("mcp_devbench.server.FilesystemManager") as mock_manager_class:
        mock_manager = AsyncMock()
        mock_manager_class.return_value = mock_manager

        from mcp_devbench.managers.filesystem_manager import FileInfo

        mock_file_info = FileInfo(
            path="/workspace/test.txt",
            size=100,
            is_dir=False,
            permissions="rw-r--r--",
            mtime=datetime.now(timezone.utc),
            etag="abc123",
            mime_type="text/plain",
        )
        mock_manager.stat = AsyncMock(return_value=mock_file_info)

        # Test fs_stat
        input_data = FileStatInput(container_id="c_test123", path="/workspace/test.txt")

        result = await server.fs_stat.fn(input_data)

        assert result.path == "/workspace/test.txt"
        assert result.size == 100
        assert result.is_dir is False
        assert result.etag == "abc123"
        assert result.mime_type == "text/plain"


@pytest.mark.asyncio
async def test_fs_list_tool():
    """Test fs_list tool endpoint."""
    from mcp_devbench import server

    with patch("mcp_devbench.server.FilesystemManager") as mock_manager_class:
        mock_manager = AsyncMock()
        mock_manager_class.return_value = mock_manager

        from mcp_devbench.managers.filesystem_manager import FileInfo

        mock_entries = [
            FileInfo(
                path="/workspace/file1.txt",
                size=100,
                is_dir=False,
                permissions="rw-r--r--",
                mtime=datetime.now(timezone.utc),
                etag="abc1",
                mime_type="text/plain",
            ),
            FileInfo(
                path="/workspace/dir1",
                size=0,
                is_dir=True,
                permissions="rwxr-xr-x",
                mtime=datetime.now(timezone.utc),
                etag="dir1",
            ),
        ]
        mock_manager.list = AsyncMock(return_value=mock_entries)

        # Test fs_list
        input_data = FileListInput(container_id="c_test123", path="/workspace")

        result = await server.fs_list.fn(input_data)

        assert result.path == "/workspace"
        assert len(result.entries) == 2
        assert result.entries[0].path == "/workspace/file1.txt"
        assert result.entries[0].is_dir is False
        assert result.entries[1].path == "/workspace/dir1"
        assert result.entries[1].is_dir is True
