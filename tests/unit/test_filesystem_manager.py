"""Unit tests for FilesystemManager."""

import base64
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from mcp_devbench.managers.filesystem_manager import FileInfo, FilesystemManager
from mcp_devbench.utils.exceptions import (
    ContainerNotFoundError,
    FileConflictError,
    FileNotFoundError,
    PathSecurityError,
)


@pytest.fixture
def mock_docker_client():
    """Create mock Docker client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_container():
    """Create mock container."""
    container = MagicMock()
    container.id = "docker123"
    return container


@pytest.fixture
def filesystem_manager(mock_docker_client):
    """Create FilesystemManager with mocked Docker client."""
    with patch("mcp_devbench.managers.filesystem_manager.get_docker_client") as mock:
        mock.return_value = mock_docker_client
        manager = FilesystemManager()
        return manager


@pytest.mark.asyncio
class TestPathValidation:
    """Tests for path validation."""

    async def test_validate_absolute_path(self, filesystem_manager):
        """Test validation of absolute paths."""
        path = filesystem_manager._validate_path("/workspace/test.txt")
        assert path == "/workspace/test.txt"

    async def test_validate_relative_path(self, filesystem_manager):
        """Test validation of relative paths."""
        path = filesystem_manager._validate_path("test.txt")
        assert path == "/workspace/test.txt"

    async def test_reject_parent_directory_escape(self, filesystem_manager):
        """Test rejection of paths trying to escape with .."""
        with pytest.raises(PathSecurityError) as exc_info:
            filesystem_manager._validate_path("/workspace/../etc/passwd")
        assert "must be under /workspace" in str(exc_info.value)

    async def test_reject_direct_escape(self, filesystem_manager):
        """Test rejection of paths outside workspace."""
        with pytest.raises(PathSecurityError) as exc_info:
            filesystem_manager._validate_path("/etc/passwd")
        assert "must be under /workspace" in str(exc_info.value)

    async def test_normalize_path_with_dots(self, filesystem_manager):
        """Test normalization of paths with . components."""
        path = filesystem_manager._validate_path("/workspace/./subdir/./test.txt")
        assert path == "/workspace/subdir/test.txt"


@pytest.mark.asyncio
class TestReadOperation:
    """Tests for read operation."""

    async def test_read_existing_file(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test reading an existing file."""
        # Setup mocks
        mock_docker_client.containers.get.return_value = mock_container
        
        # Mock stat command output
        stat_output = MagicMock()
        stat_output.exit_code = 0
        stat_output.output = b"13|644|1609459200"  # size|perms|mtime
        
        # Mock read command output
        read_output = MagicMock()
        read_output.exit_code = 0
        read_output.output = b"Hello, World!"
        
        # Mock is_dir check
        is_dir_output = MagicMock()
        is_dir_output.exit_code = 0
        is_dir_output.output = b"no"
        
        mock_container.exec_run.side_effect = [
            stat_output,
            read_output,
            is_dir_output,
        ]

        # Execute
        content, file_info = await filesystem_manager.read("c_test123", "test.txt")

        # Verify
        assert content == b"Hello, World!"
        assert file_info.path == "/workspace/test.txt"
        assert file_info.size == 13
        assert file_info.is_dir is False
        assert file_info.permissions == "644"
        assert isinstance(file_info.etag, str)
        assert len(file_info.etag) == 32  # MD5 hash

    async def test_read_nonexistent_file(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test reading a nonexistent file."""
        # Setup mocks
        mock_docker_client.containers.get.return_value = mock_container
        
        stat_output = MagicMock()
        stat_output.exit_code = 1
        mock_container.exec_run.return_value = stat_output

        # Execute and verify
        with pytest.raises(FileNotFoundError):
            await filesystem_manager.read("c_test123", "nonexistent.txt")

    async def test_read_with_invalid_path(self, filesystem_manager):
        """Test reading with invalid path."""
        with pytest.raises(PathSecurityError):
            await filesystem_manager.read("c_test123", "/etc/passwd")


@pytest.mark.asyncio
class TestWriteOperation:
    """Tests for write operation."""

    async def test_write_new_file(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test writing a new file."""
        # Setup mocks
        mock_docker_client.containers.get.return_value = mock_container
        
        # Mock write command
        write_output = MagicMock()
        write_output.exit_code = 0
        
        # Mock stat command for etag calculation
        stat_output = MagicMock()
        stat_output.exit_code = 0
        stat_output.output = b"1609459200"  # mtime
        
        mock_container.exec_run.side_effect = [
            write_output,
            stat_output,
        ]

        # Execute
        content = b"Hello, World!"
        etag = await filesystem_manager.write("c_test123", "test.txt", content)

        # Verify
        assert isinstance(etag, str)
        assert len(etag) == 32  # MD5 hash

    async def test_write_with_parent_directory_creation(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test writing file creates parent directories."""
        # Setup mocks
        mock_docker_client.containers.get.return_value = mock_container
        
        mkdir_output = MagicMock()
        mkdir_output.exit_code = 0
        
        write_output = MagicMock()
        write_output.exit_code = 0
        
        stat_output = MagicMock()
        stat_output.exit_code = 0
        stat_output.output = b"1609459200"
        
        mock_container.exec_run.side_effect = [
            mkdir_output,
            write_output,
            stat_output,
        ]

        # Execute
        content = b"test"
        await filesystem_manager.write("c_test123", "subdir/test.txt", content)

        # Verify mkdir was called
        calls = mock_container.exec_run.call_args_list
        assert any("mkdir -p" in str(call) for call in calls)

    async def test_write_with_etag_mismatch(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test write fails with mismatched ETag."""
        # Setup mocks for read operation
        mock_docker_client.containers.get.return_value = mock_container
        
        stat_output = MagicMock()
        stat_output.exit_code = 0
        stat_output.output = b"5|644|1609459200"
        
        read_output = MagicMock()
        read_output.exit_code = 0
        read_output.output = b"hello"
        
        is_dir_output = MagicMock()
        is_dir_output.exit_code = 0
        is_dir_output.output = b"no"
        
        mock_container.exec_run.side_effect = [
            stat_output,
            read_output,
            is_dir_output,
        ]

        # Execute and verify
        with pytest.raises(FileConflictError):
            await filesystem_manager.write(
                "c_test123",
                "test.txt",
                b"new content",
                if_match_etag="wrong_etag"
            )


@pytest.mark.asyncio
class TestDeleteOperation:
    """Tests for delete operation."""

    async def test_delete_existing_file(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test deleting an existing file."""
        # Setup mocks
        mock_docker_client.containers.get.return_value = mock_container
        
        delete_output = MagicMock()
        delete_output.exit_code = 0
        mock_container.exec_run.return_value = delete_output

        # Execute
        await filesystem_manager.delete("c_test123", "test.txt")

        # Verify rm command was called
        mock_container.exec_run.assert_called_once()
        call_args = mock_container.exec_run.call_args
        assert "rm -rf" in str(call_args)

    async def test_delete_nonexistent_file(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test deleting nonexistent file raises error."""
        # Setup mocks
        mock_docker_client.containers.get.return_value = mock_container
        
        # rm fails
        delete_output = MagicMock()
        delete_output.exit_code = 1
        
        # test -e also fails (file doesn't exist)
        test_output = MagicMock()
        test_output.exit_code = 1
        
        mock_container.exec_run.side_effect = [delete_output, test_output]

        # Execute and verify
        with pytest.raises(FileNotFoundError):
            await filesystem_manager.delete("c_test123", "nonexistent.txt")

    async def test_delete_workspace_root_forbidden(self, filesystem_manager):
        """Test deleting workspace root is forbidden."""
        with pytest.raises(PathSecurityError) as exc_info:
            await filesystem_manager.delete("c_test123", "/workspace")
        assert "Cannot delete workspace root" in str(exc_info.value)


@pytest.mark.asyncio
class TestStatOperation:
    """Tests for stat operation."""

    async def test_stat_existing_file(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test getting stats for existing file."""
        # Setup mocks
        mock_docker_client.containers.get.return_value = mock_container
        
        # Mock stat command
        stat_output = MagicMock()
        stat_output.exit_code = 0
        stat_output.output = b"13|644|1609459200|regular file"
        
        # Mock read for etag (called by stat for files)
        read_stat_output = MagicMock()
        read_stat_output.exit_code = 0
        read_stat_output.output = b"13|644|1609459200"
        
        read_output = MagicMock()
        read_output.exit_code = 0
        read_output.output = b"Hello, World!"
        
        is_dir_output = MagicMock()
        is_dir_output.exit_code = 0
        is_dir_output.output = b"no"
        
        mock_container.exec_run.side_effect = [
            stat_output,
            read_stat_output,
            read_output,
            is_dir_output,
        ]

        # Execute
        file_info = await filesystem_manager.stat("c_test123", "test.txt")

        # Verify
        assert file_info.path == "/workspace/test.txt"
        assert file_info.size == 13
        assert file_info.is_dir is False
        assert file_info.permissions == "644"
        assert isinstance(file_info.etag, str)

    async def test_stat_directory(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test getting stats for directory."""
        # Setup mocks
        mock_docker_client.containers.get.return_value = mock_container
        
        stat_output = MagicMock()
        stat_output.exit_code = 0
        stat_output.output = b"4096|755|1609459200|directory"
        mock_container.exec_run.return_value = stat_output

        # Execute
        file_info = await filesystem_manager.stat("c_test123", "subdir")

        # Verify
        assert file_info.path == "/workspace/subdir"
        assert file_info.is_dir is True


@pytest.mark.asyncio
class TestListOperation:
    """Tests for list operation."""

    async def test_list_directory(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test listing directory contents."""
        # Setup mocks
        mock_docker_client.containers.get.return_value = mock_container
        
        list_output = MagicMock()
        list_output.exit_code = 0
        list_output.output = (
            b"/workspace/file1.txt|100|644|1609459200.0|f\n"
            b"/workspace/file2.py|200|644|1609459200.0|f\n"
            b"/workspace/subdir|4096|755|1609459200.0|d\n"
        )
        mock_container.exec_run.return_value = list_output

        # Execute
        files = await filesystem_manager.list("c_test123", "/workspace")

        # Verify
        assert len(files) == 3
        assert files[0].path == "/workspace/file1.txt"
        assert files[0].size == 100
        assert files[0].is_dir is False
        assert files[2].path == "/workspace/subdir"
        assert files[2].is_dir is True

    async def test_list_empty_directory(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test listing empty directory."""
        # Setup mocks
        mock_docker_client.containers.get.return_value = mock_container
        
        list_output = MagicMock()
        list_output.exit_code = 0
        list_output.output = b""
        mock_container.exec_run.return_value = list_output

        # Execute
        files = await filesystem_manager.list("c_test123", "/workspace")

        # Verify
        assert len(files) == 0

    async def test_list_nonexistent_directory(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test listing nonexistent directory."""
        # Setup mocks
        mock_docker_client.containers.get.return_value = mock_container
        
        # find fails
        list_output = MagicMock()
        list_output.exit_code = 1
        
        # test -d also fails
        test_output = MagicMock()
        test_output.exit_code = 1
        
        mock_container.exec_run.side_effect = [list_output, test_output]

        # Execute and verify
        with pytest.raises(FileNotFoundError):
            await filesystem_manager.list("c_test123", "/workspace/nonexistent")


class TestMimeTypeGuessing:
    """Tests for MIME type guessing."""

    def test_guess_text_mime_type(self, filesystem_manager):
        """Test guessing MIME type for text files."""
        mime = filesystem_manager._guess_mime_type("test.txt")
        assert mime == "text/plain"

    def test_guess_python_mime_type(self, filesystem_manager):
        """Test guessing MIME type for Python files."""
        mime = filesystem_manager._guess_mime_type("script.py")
        assert mime == "text/x-python"

    def test_guess_json_mime_type(self, filesystem_manager):
        """Test guessing MIME type for JSON files."""
        mime = filesystem_manager._guess_mime_type("data.json")
        assert mime == "application/json"

    def test_guess_unknown_mime_type(self, filesystem_manager):
        """Test guessing MIME type for unknown files."""
        mime = filesystem_manager._guess_mime_type("file.xyz")
        assert mime == "application/octet-stream"


@pytest.mark.asyncio
class TestContainerNotFound:
    """Tests for container not found errors."""

    async def test_operations_with_nonexistent_container(
        self, filesystem_manager, mock_docker_client
    ):
        """Test operations fail with nonexistent container."""
        from docker.errors import NotFound
        
        mock_docker_client.containers.get.side_effect = NotFound("Container not found")

        with pytest.raises(ContainerNotFoundError):
            await filesystem_manager.read("c_nonexistent", "test.txt")

        with pytest.raises(ContainerNotFoundError):
            await filesystem_manager.write("c_nonexistent", "test.txt", b"content")

        with pytest.raises(ContainerNotFoundError):
            await filesystem_manager.delete("c_nonexistent", "test.txt")

        with pytest.raises(ContainerNotFoundError):
            await filesystem_manager.stat("c_nonexistent", "test.txt")

        with pytest.raises(ContainerNotFoundError):
            await filesystem_manager.list("c_nonexistent", "/workspace")
