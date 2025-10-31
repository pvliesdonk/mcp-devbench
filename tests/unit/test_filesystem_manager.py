"""Unit tests for FilesystemManager."""

from unittest.mock import MagicMock, patch

import pytest

from mcp_devbench.managers.filesystem_manager import (
    BatchOperation,
    FilesystemManager,
    OperationType,
)
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


@pytest.mark.asyncio
class TestBatchOperations:
    """Tests for batch operations."""

    async def test_batch_read_operations(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test batch read operations."""
        mock_docker_client.containers.get.return_value = mock_container

        # Setup mocks for read operations
        def exec_side_effect(*args, **kwargs):
            cmd = args[0]
            if "stat" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"13|644|1609459200"
                return result
            elif "cat" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"test content"
                return result
            elif "test -d" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"no"
                return result
            elif "mkdir" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            elif "rm -rf" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            return MagicMock(exit_code=0)

        mock_container.exec_run.side_effect = exec_side_effect

        # Execute batch
        operations = [
            BatchOperation(op_type=OperationType.READ, path="file1.txt"),
            BatchOperation(op_type=OperationType.READ, path="file2.txt"),
        ]
        result = await filesystem_manager.batch("c_test123", operations)

        # Verify
        assert result.success is True
        assert len(result.results) == 2
        assert all(r.success for r in result.results)
        assert result.results[0].data["content"] == b"test content"

    async def test_batch_write_operations(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test batch write operations."""
        mock_docker_client.containers.get.return_value = mock_container

        write_count = [0]

        def exec_side_effect(*args, **kwargs):
            cmd = args[0]
            if "base64 -d" in str(cmd):
                write_count[0] += 1
                result = MagicMock()
                result.exit_code = 0
                return result
            elif "stat -c '%s|%a|%Y'" in str(cmd):
                # For checking if file exists before write (for rollback)
                result = MagicMock()
                result.exit_code = 1  # File doesn't exist yet
                return result
            elif "stat -c '%Y'" in str(cmd):
                # For getting mtime after write
                result = MagicMock()
                result.exit_code = 0
                result.output = b"1609459200"
                return result
            elif "mkdir" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            elif "rm -rf" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            return MagicMock(exit_code=0)

        mock_container.exec_run.side_effect = exec_side_effect

        # Execute batch
        operations = [
            BatchOperation(
                op_type=OperationType.WRITE, path="file1.txt", content=b"content1"
            ),
            BatchOperation(
                op_type=OperationType.WRITE, path="file2.txt", content=b"content2"
            ),
        ]
        result = await filesystem_manager.batch("c_test123", operations)

        # Verify
        assert result.success is True
        assert len(result.results) == 2
        assert all(r.success for r in result.results)
        assert write_count[0] == 2

    async def test_batch_mixed_operations(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test batch with mixed operations."""
        mock_docker_client.containers.get.return_value = mock_container

        def exec_side_effect(*args, **kwargs):
            cmd = args[0]
            if "stat -c '%s|%a|%Y'" in str(cmd) and "file1.txt" in str(cmd):
                # Read operation for file1.txt
                result = MagicMock()
                result.exit_code = 0
                result.output = b"13|644|1609459200"
                return result
            elif "cat" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"test content"
                return result
            elif "test -d" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"no"
                return result
            elif "base64 -d" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            elif "stat -c '%s|%a|%Y'" in str(cmd) and "file2.txt" in str(cmd):
                # Check before write - file doesn't exist
                result = MagicMock()
                result.exit_code = 1
                return result
            elif "stat -c '%s|%a|%Y'" in str(cmd) and "file3.txt" in str(cmd):
                # Check before delete - file doesn't exist
                result = MagicMock()
                result.exit_code = 1
                return result
            elif "stat -c '%Y'" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"1609459200"
                return result
            elif "rm -rf" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            elif "mkdir" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            return MagicMock(exit_code=0)

        mock_container.exec_run.side_effect = exec_side_effect

        # Execute batch
        operations = [
            BatchOperation(op_type=OperationType.READ, path="file1.txt"),
            BatchOperation(
                op_type=OperationType.WRITE, path="file2.txt", content=b"new content"
            ),
            BatchOperation(op_type=OperationType.DELETE, path="file3.txt"),
        ]
        result = await filesystem_manager.batch("c_test123", operations)

        # Verify
        assert result.success is True
        assert len(result.results) == 3
        assert all(r.success for r in result.results)

    async def test_batch_copy_operation(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test batch copy operation."""
        mock_docker_client.containers.get.return_value = mock_container

        def exec_side_effect(*args, **kwargs):
            cmd = args[0]
            if "stat" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"13|644|1609459200"
                return result
            elif "cat" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"source content"
                return result
            elif "test -d" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"no"
                return result
            elif "base64 -d" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            elif "mkdir" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            elif "rm -rf" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            return MagicMock(exit_code=0)

        mock_container.exec_run.side_effect = exec_side_effect

        # Execute batch
        operations = [
            BatchOperation(
                op_type=OperationType.COPY,
                path="source.txt",
                dest_path="dest.txt",
            )
        ]
        result = await filesystem_manager.batch("c_test123", operations)

        # Verify
        assert result.success is True
        assert len(result.results) == 1
        assert result.results[0].success is True
        assert result.results[0].data["dest_path"] == "dest.txt"

    async def test_batch_move_operation(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test batch move operation."""
        mock_docker_client.containers.get.return_value = mock_container

        def exec_side_effect(*args, **kwargs):
            cmd = args[0]
            if "stat" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"13|644|1609459200"
                return result
            elif "cat" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"source content"
                return result
            elif "test -d" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"no"
                return result
            elif "base64 -d" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            elif "rm -rf" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            elif "mkdir" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            return MagicMock(exit_code=0)

        mock_container.exec_run.side_effect = exec_side_effect

        # Execute batch
        operations = [
            BatchOperation(
                op_type=OperationType.MOVE,
                path="source.txt",
                dest_path="dest.txt",
            )
        ]
        result = await filesystem_manager.batch("c_test123", operations)

        # Verify
        assert result.success is True
        assert len(result.results) == 1
        assert result.results[0].success is True

    async def test_batch_with_etag_conflict(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test batch fails fast on ETag conflict."""
        mock_docker_client.containers.get.return_value = mock_container

        # Mock read to return existing file with different etag
        def exec_side_effect(*args, **kwargs):
            cmd = args[0]
            if "stat" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"5|644|1609459200"
                return result
            elif "cat" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"hello"
                return result
            elif "test -d" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                result.output = b"no"
                return result
            elif "mkdir" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            return MagicMock(exit_code=0)

        mock_container.exec_run.side_effect = exec_side_effect

        # Execute batch with wrong etag
        operations = [
            BatchOperation(
                op_type=OperationType.WRITE,
                path="file.txt",
                content=b"new content",
                if_match_etag="wrong_etag",
            )
        ]
        result = await filesystem_manager.batch("c_test123", operations)

        # Verify it failed before executing
        assert result.success is False
        assert len(result.results) == 0
        assert "ETag mismatch" in result.error

    async def test_batch_rollback_on_failure(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test batch rolls back on failure."""
        mock_docker_client.containers.get.return_value = mock_container

        call_count = [0]

        def exec_side_effect(*args, **kwargs):
            cmd = args[0]
            call_count[0] += 1

            # First operation: write file1.txt
            if "stat -c '%s|%a|%Y'" in str(cmd) and "file1.txt" in str(cmd):
                # File doesn't exist yet
                result = MagicMock()
                result.exit_code = 1
                return result
            elif "base64 -d" in str(cmd) and call_count[0] <= 5:
                # First write succeeds
                result = MagicMock()
                result.exit_code = 0
                return result
            elif "stat -c '%Y'" in str(cmd) and call_count[0] <= 6:
                result = MagicMock()
                result.exit_code = 0
                result.output = b"1609459200"
                return result

            # Second operation: write file2.txt (this will fail)
            elif "stat -c '%s|%a|%Y'" in str(cmd) and "file2.txt" in str(cmd):
                # File doesn't exist yet
                result = MagicMock()
                result.exit_code = 1
                return result
            elif "base64 -d" in str(cmd):
                # Second write fails
                result = MagicMock()
                result.exit_code = 1
                result.output = b"Error"
                return result

            elif "mkdir" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            elif "rm -rf" in str(cmd):
                result = MagicMock()
                result.exit_code = 0
                return result
            else:
                result = MagicMock()
                result.exit_code = 0
                return result

        mock_container.exec_run.side_effect = exec_side_effect

        # Execute batch where second operation fails
        operations = [
            BatchOperation(
                op_type=OperationType.WRITE, path="file1.txt", content=b"content1"
            ),
            BatchOperation(
                op_type=OperationType.WRITE, path="file2.txt", content=b"content2"
            ),
        ]
        result = await filesystem_manager.batch("c_test123", operations)

        # Verify rollback was performed
        assert result.success is False
        assert result.rollback_performed is True
        assert len(result.results) == 2  # First succeeded, second failed

    async def test_batch_with_invalid_path(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test batch fails on invalid path."""
        mock_docker_client.containers.get.return_value = mock_container

        # Execute batch with invalid path
        operations = [
            BatchOperation(
                op_type=OperationType.WRITE,
                path="/etc/passwd",  # Outside workspace
                content=b"bad",
            )
        ]

        result = await filesystem_manager.batch("c_test123", operations)

        # Verify it failed
        assert result.success is False


@pytest.mark.asyncio
class TestImportExportOperations:
    """Tests for import/export operations."""

    async def test_export_tar_basic(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test basic tar export."""
        mock_docker_client.containers.get.return_value = mock_container

        # Mock tar command output
        tar_data = b"fake tar data"

        exec_result = MagicMock()
        exec_result.output = iter([tar_data])
        mock_container.exec_run.return_value = exec_result

        # Execute export
        chunks = []
        async for chunk in filesystem_manager.export_tar("c_test123", "/workspace"):
            chunks.append(chunk)

        # Verify
        assert len(chunks) == 1
        assert chunks[0] == tar_data

    async def test_export_tar_with_compression(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test tar export with compression."""
        mock_docker_client.containers.get.return_value = mock_container

        tar_data = b"compressed tar data"

        exec_result = MagicMock()
        exec_result.output = iter([tar_data])
        mock_container.exec_run.return_value = exec_result

        # Execute export with compression
        chunks = []
        async for chunk in filesystem_manager.export_tar(
            "c_test123", "/workspace", compress=True
        ):
            chunks.append(chunk)

        # Verify
        assert len(chunks) == 1
        # Verify compression flag was used in command
        call_args = mock_container.exec_run.call_args
        assert "-z" in str(call_args) or "czf" in str(call_args)

    async def test_export_tar_streaming(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test tar export streams data in chunks."""
        mock_docker_client.containers.get.return_value = mock_container

        # Multiple chunks
        chunks_data = [b"chunk1", b"chunk2", b"chunk3"]

        exec_result = MagicMock()
        exec_result.output = iter(chunks_data)
        mock_container.exec_run.return_value = exec_result

        # Execute export
        received_chunks = []
        async for chunk in filesystem_manager.export_tar("c_test123", "/workspace"):
            received_chunks.append(chunk)

        # Verify all chunks received
        assert len(received_chunks) == 3
        assert received_chunks == chunks_data

    async def test_import_tar_basic(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test basic tar import."""
        mock_docker_client.containers.get.return_value = mock_container

        # Create a simple tar in memory
        import io
        import tarfile

        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            # Add a simple file
            file_data = b"test content"
            file_info = tarfile.TarInfo(name="test.txt")
            file_info.size = len(file_data)
            tar.addfile(file_info, io.BytesIO(file_data))

        tar_data = tar_buffer.getvalue()

        # Mock exec commands
        def exec_side_effect(*args, **kwargs):
            result = MagicMock()
            result.exit_code = 0
            cmd = args[0] if args else ""
            if "wc -l" in str(cmd):
                result.output = b"1"  # 1 file created
            return result

        mock_container.exec_run.side_effect = exec_side_effect

        # Execute import
        result = await filesystem_manager.import_tar(
            "c_test123", "/workspace", tar_data=tar_data
        )

        # Verify
        assert result["bytes_written"] == len(tar_data)
        assert result["files_created"] == 1
        assert result["dest_path"] == "/workspace"

    async def test_import_tar_with_streaming(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test tar import with streaming."""
        mock_docker_client.containers.get.return_value = mock_container

        # Create tar data
        import io
        import tarfile

        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            file_data = b"streamed content"
            file_info = tarfile.TarInfo(name="streamed.txt")
            file_info.size = len(file_data)
            tar.addfile(file_info, io.BytesIO(file_data))

        tar_data = tar_buffer.getvalue()

        # Create async iterator for streaming
        async def tar_stream():
            # Split into chunks
            chunk_size = 100
            for i in range(0, len(tar_data), chunk_size):
                yield tar_data[i : i + chunk_size]

        # Mock exec commands
        def exec_side_effect(*args, **kwargs):
            result = MagicMock()
            result.exit_code = 0
            cmd = args[0] if args else ""
            if "wc -l" in str(cmd):
                result.output = b"1"
            return result

        mock_container.exec_run.side_effect = exec_side_effect

        # Execute import with streaming
        result = await filesystem_manager.import_tar(
            "c_test123", "/workspace", stream=tar_stream()
        )

        # Verify
        assert result["bytes_written"] == len(tar_data)
        assert result["files_created"] == 1

    async def test_import_tar_size_limit(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test tar import respects size limits."""
        mock_docker_client.containers.get.return_value = mock_container

        # Create large tar stream
        async def large_tar_stream():
            # Yield 2MB of data (exceeds 1MB limit)
            for _ in range(20):
                yield b"x" * (100 * 1024)  # 100KB chunks

        # Execute import with small size limit
        with pytest.raises(ValueError) as exc_info:
            await filesystem_manager.import_tar(
                "c_test123", "/workspace", stream=large_tar_stream(), max_size_mb=1
            )

        assert "exceeds maximum size" in str(exc_info.value)

    async def test_validate_tar_rejects_absolute_paths(
        self, filesystem_manager
    ):
        """Test tar validation rejects absolute paths."""
        import io
        import tarfile

        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            file_info = tarfile.TarInfo(name="/etc/passwd")
            file_info.size = 0
            tar.addfile(file_info, io.BytesIO(b""))

        tar_data = tar_buffer.getvalue()

        # Validate should fail
        with pytest.raises(PathSecurityError) as exc_info:
            await filesystem_manager._validate_tar_contents(tar_data, "/workspace")

        assert "absolute paths" in str(exc_info.value)

    async def test_validate_tar_rejects_parent_refs(
        self, filesystem_manager
    ):
        """Test tar validation rejects parent directory references."""
        import io
        import tarfile

        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            file_info = tarfile.TarInfo(name="../etc/passwd")
            file_info.size = 0
            tar.addfile(file_info, io.BytesIO(b""))

        tar_data = tar_buffer.getvalue()

        # Validate should fail
        with pytest.raises(PathSecurityError) as exc_info:
            await filesystem_manager._validate_tar_contents(tar_data, "/workspace")

        assert "parent directory" in str(exc_info.value).lower()

    async def test_validate_tar_rejects_escape_attempts(
        self, filesystem_manager
    ):
        """Test tar validation prevents workspace escape."""
        import io
        import tarfile

        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            # Try to escape by using many parent refs
            file_info = tarfile.TarInfo(name="../../../etc/passwd")
            file_info.size = 0
            tar.addfile(file_info, io.BytesIO(b""))

        tar_data = tar_buffer.getvalue()

        # Validate should fail
        with pytest.raises(PathSecurityError):
            await filesystem_manager._validate_tar_contents(tar_data, "/workspace")

    async def test_validate_tar_accepts_valid_paths(
        self, filesystem_manager
    ):
        """Test tar validation accepts valid paths."""
        import io
        import tarfile

        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w") as tar:
            # Valid paths
            for name in ["file.txt", "subdir/file.txt", "./file.txt"]:
                file_info = tarfile.TarInfo(name=name)
                file_info.size = 0
                tar.addfile(file_info, io.BytesIO(b""))

        tar_data = tar_buffer.getvalue()

        # Validate should succeed (not raise)
        await filesystem_manager._validate_tar_contents(tar_data, "/workspace")

    async def test_download_file(
        self, filesystem_manager, mock_docker_client, mock_container
    ):
        """Test single file download."""
        mock_docker_client.containers.get.return_value = mock_container

        # Mock file read
        stat_output = MagicMock()
        stat_output.exit_code = 0
        stat_output.output = b"13|644|1609459200"

        read_output = MagicMock()
        read_output.exit_code = 0
        read_output.output = b"downloaded file"

        is_dir_output = MagicMock()
        is_dir_output.exit_code = 0
        is_dir_output.output = b"no"

        mock_container.exec_run.side_effect = [
            stat_output,
            read_output,
            is_dir_output,
        ]

        # Execute download
        content, file_info = await filesystem_manager.download_file(
            "c_test123", "file.txt"
        )

        # Verify
        assert content == b"downloaded file"
        assert file_info.path == "/workspace/file.txt"
        assert file_info.size == 13
