"""Filesystem manager for Docker container workspace operations."""

import hashlib
import io
import os
import posixpath
import shlex
import tarfile
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, List, Optional

from docker import DockerClient
from docker.errors import APIError, NotFound

from mcp_devbench.utils import get_logger
from mcp_devbench.utils.docker_client import get_docker_client
from mcp_devbench.utils.exceptions import (
    ContainerNotFoundError,
    DockerAPIError,
    FileConflictError,
    FileNotFoundError,
    PathSecurityError,
)

logger = get_logger(__name__)


@dataclass
class FileInfo:
    """Information about a file or directory."""

    path: str
    size: int
    is_dir: bool
    permissions: str
    mtime: datetime
    etag: str
    mime_type: Optional[str] = None


class OperationType(Enum):
    """Types of batch operations."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    MOVE = "move"
    COPY = "copy"


@dataclass
class BatchOperation:
    """A single operation in a batch."""

    op_type: OperationType
    path: str
    content: Optional[bytes] = None
    dest_path: Optional[str] = None  # For move/copy
    if_match_etag: Optional[str] = None


@dataclass
class OperationResult:
    """Result of a batch operation."""

    success: bool
    op_type: OperationType
    path: str
    data: Optional[Any] = None  # Content for read, etag for write, etc.
    error: Optional[str] = None


@dataclass
class BatchResult:
    """Result of a batch operation."""

    success: bool
    results: List[OperationResult]
    rollback_performed: bool = False
    error: Optional[str] = None


class FilesystemManager:
    """Manager for filesystem operations in Docker containers."""

    WORKSPACE_ROOT = "/workspace"

    def __init__(self) -> None:
        """Initialize filesystem manager."""
        self.docker_client: DockerClient = get_docker_client()

    def _validate_path(self, path: str) -> str:
        """
        Validate and normalize a path to ensure it's within workspace.

        Args:
            path: Path to validate

        Returns:
            Normalized absolute path

        Raises:
            PathSecurityError: If path is invalid or escapes workspace
        """
        # Normalize the path
        if not path.startswith("/"):
            path = posixpath.join(self.WORKSPACE_ROOT, path)

        # Normalize to resolve . and ..
        normalized = posixpath.normpath(path)

        # Check if path tries to escape workspace
        if not normalized.startswith(self.WORKSPACE_ROOT):
            raise PathSecurityError(
                path, f"Path must be under {self.WORKSPACE_ROOT}"
            )

        # Check for .. components (should be caught by normpath, but double-check)
        if ".." in normalized.split(posixpath.sep):
            raise PathSecurityError(path, "Path contains '..' components")

        return normalized

    def _get_container(self, container_id: str):
        """
        Get Docker container by ID.

        Args:
            container_id: Container ID

        Returns:
            Docker container object

        Raises:
            ContainerNotFoundError: If container not found
        """
        try:
            return self.docker_client.containers.get(container_id)
        except NotFound:
            raise ContainerNotFoundError(container_id)
        except APIError as e:
            raise DockerAPIError(f"Failed to get container: {e}", e)

    def _calculate_etag(self, content: bytes, mtime: Optional[str] = None) -> str:
        """
        Calculate ETag for file content.

        Args:
            content: File content (bytes or str)
            mtime: Optional modification time (str)

        Returns:
            ETag string (SHA-256 hash)
        """
        # Ensure content is bytes
        if isinstance(content, str):
            hash_input = content.encode('utf-8')
        elif isinstance(content, bytes):
            hash_input = content
        else:
            # Handle other types (e.g., Mock objects in tests)
            hash_input = str(content).encode('utf-8')

        if mtime:
            if isinstance(mtime, str):
                hash_input += mtime.encode('utf-8')
            elif isinstance(mtime, bytes):
                hash_input += mtime
            else:
                # Handle other types
                hash_input += str(mtime).encode('utf-8')

        return hashlib.sha256(hash_input).hexdigest()

    async def read(
        self, container_id: str, path: str
    ) -> tuple[bytes, FileInfo]:
        """
        Read file from container workspace.

        Args:
            container_id: Container ID
            path: File path

        Returns:
            Tuple of (file content, file info)

        Raises:
            ContainerNotFoundError: If container not found
            FileNotFoundError: If file not found
            PathSecurityError: If path is invalid
            DockerAPIError: If Docker operations fail
        """
        normalized_path = self._validate_path(path)
        container = self._get_container(container_id)

        try:
            # First get file stats
            stat_cmd = f"stat -c '%s|%a|%Y' {shlex.quote(normalized_path)}"
            exec_result = container.exec_run(
                ["sh", "-c", stat_cmd],
                user="1000:1000"
            )

            if exec_result.exit_code != 0:
                raise FileNotFoundError(path)

            # Parse stat output: size|permissions|mtime
            stat_output = exec_result.output.decode().strip()
            size_str, perms, mtime_str = stat_output.split("|")
            size = int(size_str)
            mtime = datetime.fromtimestamp(int(mtime_str))

            # Read file content
            read_cmd = f"cat {shlex.quote(normalized_path)}"
            exec_result = container.exec_run(
                ["sh", "-c", read_cmd],
                user="1000:1000"
            )

            if exec_result.exit_code != 0:
                raise FileNotFoundError(path)

            content = exec_result.output

            # Calculate etag
            etag = self._calculate_etag(content, mtime_str)

            # Determine if it's a directory
            is_dir_cmd = f"test -d {shlex.quote(normalized_path)} && echo 'yes' || echo 'no'"
            is_dir_result = container.exec_run(
                ["sh", "-c", is_dir_cmd],
                user="1000:1000"
            )
            is_dir = is_dir_result.output.decode().strip() == "yes"

            file_info = FileInfo(
                path=normalized_path,
                size=size,
                is_dir=is_dir,
                permissions=perms,
                mtime=mtime,
                etag=etag,
                mime_type=self._guess_mime_type(normalized_path) if not is_dir else None
            )

            logger.info(f"Read file {normalized_path} from container {container_id}")
            return content, file_info

        except (NotFound, APIError) as e:
            if isinstance(e, NotFound) or "No such file" in str(e):
                raise FileNotFoundError(path)
            raise DockerAPIError(f"Failed to read file: {e}", e)

    async def write(
        self,
        container_id: str,
        path: str,
        content: bytes,
        if_match_etag: Optional[str] = None,
    ) -> str:
        """
        Write file to container workspace.

        Args:
            container_id: Container ID
            path: File path
            content: File content
            if_match_etag: Optional ETag to check before writing

        Returns:
            New ETag for the file

        Raises:
            ContainerNotFoundError: If container not found
            FileConflictError: If ETag doesn't match
            PathSecurityError: If path is invalid
            DockerAPIError: If Docker operations fail
        """
        normalized_path = self._validate_path(path)
        container = self._get_container(container_id)

        try:
            # Check etag if provided
            if if_match_etag:
                try:
                    _, existing_info = await self.read(container_id, path)
                    if existing_info.etag != if_match_etag:
                        raise FileConflictError(
                            path, if_match_etag, existing_info.etag
                        )
                except FileNotFoundError:
                    # File doesn't exist, that's ok for new files
                    pass

            # Create parent directories if needed
            parent_dir = posixpath.dirname(normalized_path)
            if parent_dir != self.WORKSPACE_ROOT:
                mkdir_cmd = f"mkdir -p {shlex.quote(parent_dir)}"
                container.exec_run(
                    ["sh", "-c", mkdir_cmd],
                    user="1000:1000"
                )

            # Write file using Docker's put_archive API to avoid command line limits
            # This works with large files (tested up to 1GB+)
            tarstream = io.BytesIO()
            with tarfile.open(fileobj=tarstream, mode='w') as tar:
                tarinfo = tarfile.TarInfo(name=posixpath.basename(normalized_path))
                tarinfo.size = len(content)
                tarinfo.mtime = int(datetime.now().timestamp())
                tarinfo.mode = 0o644  # rw-r--r--
                tarinfo.uid = 1000
                tarinfo.gid = 1000
                tar.addfile(tarinfo, io.BytesIO(content))

            tarstream.seek(0)
            # put_archive expects the path to the directory where to extract
            success = container.put_archive(
                path=parent_dir if parent_dir else self.WORKSPACE_ROOT,
                data=tarstream.getvalue()
            )

            if not success:
                raise DockerAPIError(
                    "Failed to write file: put_archive returned False"
                )

            # Get mtime and calculate new etag
            stat_cmd = f"stat -c '%Y' {shlex.quote(normalized_path)}"
            stat_result = container.exec_run(
                ["sh", "-c", stat_cmd],
                user="1000:1000"
            )
            mtime_str = stat_result.output.decode().strip()
            new_etag = self._calculate_etag(content, mtime_str)

            logger.info(f"Wrote file {normalized_path} to container {container_id}")
            return new_etag

        except APIError as e:
            raise DockerAPIError(f"Failed to write file: {e}", e)

    async def delete(self, container_id: str, path: str) -> None:
        """
        Delete file or directory from container workspace.

        Args:
            container_id: Container ID
            path: File or directory path

        Raises:
            ContainerNotFoundError: If container not found
            FileNotFoundError: If file not found
            PathSecurityError: If path is invalid
            DockerAPIError: If Docker operations fail
        """
        normalized_path = self._validate_path(path)
        container = self._get_container(container_id)

        # Don't allow deleting the workspace root itself
        if normalized_path == self.WORKSPACE_ROOT:
            raise PathSecurityError(path, "Cannot delete workspace root")

        try:
            # Use rm -rf to handle both files and directories
            delete_cmd = f"rm -rf {shlex.quote(normalized_path)}"
            exec_result = container.exec_run(
                ["sh", "-c", delete_cmd],
                user="1000:1000"
            )

            if exec_result.exit_code != 0:
                # Check if file exists
                test_cmd = f"test -e {shlex.quote(normalized_path)}"
                test_result = container.exec_run(
                    ["sh", "-c", test_cmd],
                    user="1000:1000"
                )
                if test_result.exit_code != 0:
                    raise FileNotFoundError(path)
                raise DockerAPIError(
                    f"Failed to delete file: {exec_result.output.decode()}"
                )

            logger.info(f"Deleted {normalized_path} from container {container_id}")

        except APIError as e:
            raise DockerAPIError(f"Failed to delete file: {e}", e)

    async def stat(self, container_id: str, path: str) -> FileInfo:
        """
        Get file or directory information.

        Args:
            container_id: Container ID
            path: File or directory path

        Returns:
            File information

        Raises:
            ContainerNotFoundError: If container not found
            FileNotFoundError: If file not found
            PathSecurityError: If path is invalid
            DockerAPIError: If Docker operations fail
        """
        normalized_path = self._validate_path(path)
        container = self._get_container(container_id)

        try:
            # Get file stats including type
            stat_cmd = (
                f"stat -c '%s|%a|%Y|%F' {shlex.quote(normalized_path)} 2>/dev/null || "
                f"echo 'NOTFOUND'"
            )
            exec_result = container.exec_run(
                ["sh", "-c", stat_cmd],
                user="1000:1000"
            )

            output = exec_result.output.decode().strip()
            if output == "NOTFOUND" or exec_result.exit_code != 0:
                raise FileNotFoundError(path)

            # Parse stat output: size|permissions|mtime|type
            size_str, perms, mtime_str, file_type = output.split("|")
            size = int(size_str)
            mtime = datetime.fromtimestamp(int(mtime_str))
            is_dir = "directory" in file_type.lower()

            # For files, calculate etag from metadata (no need to read content)
            etag = ""
            if not is_dir:
                etag = hashlib.sha256(
                    f"{normalized_path}:{size}:{mtime_str}".encode()
                ).hexdigest()
            else:
                # For directories, use a simple hash
                etag = hashlib.sha256(
                    f"{normalized_path}:{mtime_str}".encode()
                ).hexdigest()

            file_info = FileInfo(
                path=normalized_path,
                size=size,
                is_dir=is_dir,
                permissions=perms,
                mtime=mtime,
                etag=etag,
                mime_type=self._guess_mime_type(normalized_path) if not is_dir else None
            )

            logger.info(f"Got stats for {normalized_path} in container {container_id}")
            return file_info

        except APIError as e:
            raise DockerAPIError(f"Failed to stat file: {e}", e)

    async def list(
        self, container_id: str, path: str = WORKSPACE_ROOT
    ) -> List[FileInfo]:
        """
        List files in directory.

        Args:
            container_id: Container ID
            path: Directory path (defaults to workspace root)

        Returns:
            List of file information objects

        Raises:
            ContainerNotFoundError: If container not found
            FileNotFoundError: If directory not found
            PathSecurityError: If path is invalid
            DockerAPIError: If Docker operations fail
        """
        normalized_path = self._validate_path(path)
        container = self._get_container(container_id)

        try:
            # Use find with specific format to get all file info at once
            # Format: path|size|perms|mtime|type
            list_cmd = (
                f"find {shlex.quote(normalized_path)} -maxdepth 1 -mindepth 1 "
                f"-printf '%p|%s|%m|%T@|%y\\n' 2>/dev/null"
            )
            exec_result = container.exec_run(
                ["sh", "-c", list_cmd],
                user="1000:1000"
            )

            if exec_result.exit_code != 0:
                # Check if directory exists
                test_cmd = f"test -d {shlex.quote(normalized_path)}"
                test_result = container.exec_run(
                    ["sh", "-c", test_cmd],
                    user="1000:1000"
                )
                if test_result.exit_code != 0:
                    raise FileNotFoundError(path)
                # Directory exists but might be empty
                return []

            output = exec_result.output.decode().strip()
            if not output:
                return []

            files = []
            for line in output.split("\n"):
                if not line:
                    continue

                parts = line.split("|")
                if len(parts) != 5:
                    continue

                file_path, size_str, perms, mtime_str, file_type = parts

                # Parse mtime (format is timestamp with decimals)
                mtime_float = float(mtime_str)
                mtime = datetime.fromtimestamp(mtime_float)

                is_dir = file_type == "d"
                size = int(size_str) if not is_dir else 0

                # Calculate a simple etag
                etag = hashlib.sha256(
                    f"{file_path}:{size}:{mtime_str}".encode()
                ).hexdigest()

                file_info = FileInfo(
                    path=file_path,
                    size=size,
                    is_dir=is_dir,
                    permissions=perms,
                    mtime=mtime,
                    etag=etag,
                    mime_type=self._guess_mime_type(file_path) if not is_dir else None
                )
                files.append(file_info)

            logger.info(
                f"Listed {len(files)} files in {normalized_path} "
                f"in container {container_id}"
            )
            return files

        except APIError as e:
            raise DockerAPIError(f"Failed to list files: {e}", e)

    def _guess_mime_type(self, path: str) -> str:
        """
        Guess MIME type from file extension.

        Args:
            path: File path

        Returns:
            MIME type string
        """
        ext = os.path.splitext(path)[1].lower()
        mime_types = {
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".py": "text/x-python",
            ".js": "text/javascript",
            ".json": "application/json",
            ".xml": "application/xml",
            ".html": "text/html",
            ".css": "text/css",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".pdf": "application/pdf",
            ".zip": "application/zip",
            ".tar": "application/x-tar",
            ".gz": "application/gzip",
        }
        return mime_types.get(ext, "application/octet-stream")

    async def batch(
        self, container_id: str, operations: List[BatchOperation]
    ) -> BatchResult:
        """
        Execute a batch of filesystem operations atomically.

        Operations are executed in order. If any operation fails, a rollback
        is attempted (best effort) to restore the original state.

        Args:
            container_id: Container ID
            operations: List of operations to execute

        Returns:
            BatchResult with success status and results for each operation

        Raises:
            ContainerNotFoundError: If container not found
            PathSecurityError: If any path is invalid
            DockerAPIError: If Docker operations fail
        """
        container = self._get_container(container_id)
        results: List[OperationResult] = []
        staging_dir = f"/tmp/mcp_batch_{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]}"
        rollback_info: List[tuple[str, Optional[bytes]]] = []  # (path, original_content)

        try:
            # Validate all paths first
            for op in operations:
                self._validate_path(op.path)
                if op.dest_path:
                    self._validate_path(op.dest_path)

            # Check all ETags before starting
            for op in operations:
                if op.if_match_etag and op.op_type in [
                    OperationType.WRITE,
                    OperationType.DELETE,
                ]:
                    try:
                        _, existing_info = await self.read(container_id, op.path)
                        if existing_info.etag != op.if_match_etag:
                            return BatchResult(
                                success=False,
                                results=[],
                                error=f"ETag mismatch for {op.path}: "
                                f"expected {op.if_match_etag}, "
                                f"got {existing_info.etag}",
                            )
                    except FileNotFoundError:
                        # File doesn't exist yet, ok for write operations
                        if op.op_type != OperationType.WRITE:
                            return BatchResult(
                                success=False,
                                results=[],
                                error=f"File not found for operation: {op.path}",
                            )

            # Create staging directory
            mkdir_cmd = f"mkdir -p {shlex.quote(staging_dir)}"
            container.exec_run(["sh", "-c", mkdir_cmd], user="1000:1000")

            # Execute operations
            for op in operations:
                try:
                    if op.op_type == OperationType.READ:
                        content, file_info = await self.read(container_id, op.path)
                        results.append(
                            OperationResult(
                                success=True,
                                op_type=op.op_type,
                                path=op.path,
                                data={"content": content, "info": file_info},
                            )
                        )

                    elif op.op_type == OperationType.WRITE:
                        # Save original content for rollback
                        try:
                            original_content, _ = await self.read(container_id, op.path)
                            rollback_info.append((op.path, original_content))
                        except FileNotFoundError:
                            rollback_info.append((op.path, None))

                        etag = await self.write(
                            container_id, op.path, op.content, op.if_match_etag
                        )
                        results.append(
                            OperationResult(
                                success=True,
                                op_type=op.op_type,
                                path=op.path,
                                data={"etag": etag},
                            )
                        )

                    elif op.op_type == OperationType.DELETE:
                        # Save original for rollback
                        try:
                            original_content, _ = await self.read(container_id, op.path)
                            rollback_info.append((op.path, original_content))
                        except FileNotFoundError:
                            rollback_info.append((op.path, None))

                        await self.delete(container_id, op.path)
                        results.append(
                            OperationResult(
                                success=True, op_type=op.op_type, path=op.path
                            )
                        )

                    elif op.op_type == OperationType.MOVE:
                        if not op.dest_path:
                            raise ValueError("dest_path required for MOVE operation")

                        # Read source
                        content, _ = await self.read(container_id, op.path)
                        rollback_info.append((op.path, content))
                        rollback_info.append((op.dest_path, None))

                        # Write to destination
                        await self.write(container_id, op.dest_path, content)
                        # Delete source
                        await self.delete(container_id, op.path)

                        results.append(
                            OperationResult(
                                success=True,
                                op_type=op.op_type,
                                path=op.path,
                                data={"dest_path": op.dest_path},
                            )
                        )

                    elif op.op_type == OperationType.COPY:
                        if not op.dest_path:
                            raise ValueError("dest_path required for COPY operation")

                        # Read source
                        content, _ = await self.read(container_id, op.path)
                        rollback_info.append((op.dest_path, None))

                        # Write to destination
                        await self.write(container_id, op.dest_path, content)

                        results.append(
                            OperationResult(
                                success=True,
                                op_type=op.op_type,
                                path=op.path,
                                data={"dest_path": op.dest_path},
                            )
                        )

                except Exception as e:
                    # Operation failed, perform rollback
                    logger.error(
                        f"Batch operation failed at {op.path}: {e}, "
                        f"performing rollback"
                    )

                    # Best-effort rollback
                    await self._rollback_operations(
                        container_id, rollback_info
                    )

                    results.append(
                        OperationResult(
                            success=False,
                            op_type=op.op_type,
                            path=op.path,
                            error=str(e),
                        )
                    )

                    return BatchResult(
                        success=False,
                        results=results,
                        rollback_performed=True,
                        error=str(e),
                    )

            # Clean up staging directory
            cleanup_cmd = f"rm -rf {shlex.quote(staging_dir)}"
            container.exec_run(["sh", "-c", cleanup_cmd], user="1000:1000")

            logger.info(
                f"Completed batch of {len(operations)} operations "
                f"in container {container_id}"
            )
            return BatchResult(success=True, results=results)

        except Exception as e:
            logger.error(f"Batch operation failed: {e}")
            # Clean up staging directory on error
            try:
                cleanup_cmd = f"rm -rf {shlex.quote(staging_dir)}"
                container.exec_run(["sh", "-c", cleanup_cmd], user="1000:1000")
            except Exception as cleanup_exc:
                logger.warning(
                    f"Failed to clean up staging directory {staging_dir}: {cleanup_exc}"
                )

            return BatchResult(
                success=False,
                results=results,
                error=str(e),
            )

    async def _rollback_operations(
        self, container_id: str, rollback_info: List[tuple[str, Optional[bytes]]]
    ) -> None:
        """
        Rollback operations (best effort).

        Args:
            container_id: Container ID
            rollback_info: List of (path, original_content) tuples
        """
        for path, original_content in reversed(rollback_info):
            try:
                if original_content is None:
                    # File didn't exist, delete it
                    try:
                        await self.delete(container_id, path)
                    except FileNotFoundError:
                        pass  # Already doesn't exist
                else:
                    # Restore original content
                    await self.write(container_id, path, original_content)
            except Exception as e:
                logger.warning(f"Failed to rollback {path}: {e}")
                # Continue with other rollbacks

    async def export_tar(
        self,
        container_id: str,
        path: str = WORKSPACE_ROOT,
        include_globs: List[str] = None,
        exclude_globs: List[str] = None,
        compress: bool = True,
    ) -> AsyncIterator[bytes]:
        """
        Export files from container as tar archive (streaming).

        Args:
            container_id: Container ID
            path: Starting path (defaults to workspace root)
            include_globs: List of glob patterns to include (None = all)
            exclude_globs: List of glob patterns to exclude
            compress: Whether to compress with gzip

        Yields:
            Chunks of tar archive data

        Raises:
            ContainerNotFoundError: If container not found
            PathSecurityError: If path is invalid
            DockerAPIError: If Docker operations fail
        """
        normalized_path = self._validate_path(path)
        container = self._get_container(container_id)

        try:
            # Build tar command
            tar_cmd = ["tar", "-C", normalized_path]

            # Add compression if requested
            if compress:
                tar_cmd.append("-z")

            tar_cmd.append("-c")

            # Build find command for filtering
            find_parts = ["find", "."]

            # Add include patterns
            if include_globs:
                find_parts.extend(["-type", "f", "("])
                for i, pattern in enumerate(include_globs):
                    if i > 0:
                        find_parts.append("-o")
                    find_parts.extend(["-path", pattern])
                find_parts.append(")")

            # Add exclude patterns
            if exclude_globs:
                for pattern in exclude_globs:
                    find_parts.extend(["!", "-path", pattern])

            # Create the full command pipeline
            if include_globs or exclude_globs:
                # Use find to filter files, then tar
                find_cmd = " ".join(shlex.quote(p) for p in find_parts)
                full_cmd = (
                    f"cd {shlex.quote(normalized_path)} && {find_cmd} | tar -c"
                )
                if compress:
                    full_cmd += "z"
                full_cmd += " -T -"
            else:
                # Just tar everything
                tar_flags = "czf" if compress else "cf"
                full_cmd = (
                    f"tar -{tar_flags} - -C {shlex.quote(normalized_path)} ."
                )

            # Execute tar command and stream output
            exec_result = container.exec_run(
                ["sh", "-c", full_cmd],
                user="1000:1000",
                stream=True,
                demux=False,
            )

            # Stream the output in chunks (Docker handles chunking)
            for chunk in exec_result.output:
                if chunk:
                    yield chunk

            logger.info(
                f"Exported tar from {normalized_path} in container {container_id}"
            )

        except APIError as e:
            raise DockerAPIError(f"Failed to export tar: {e}", e)

    async def import_tar(
        self,
        container_id: str,
        dest: str = WORKSPACE_ROOT,
        stream: AsyncIterator[bytes] = None,
        tar_data: bytes = None,
        max_size_mb: int = 1024,
    ) -> dict:
        """
        Import tar archive into container workspace.

        Args:
            container_id: Container ID
            dest: Destination path (defaults to workspace root)
            stream: Async iterator of tar data chunks (for streaming)
            tar_data: Complete tar data (alternative to stream)
            max_size_mb: Maximum allowed size in MB

        Returns:
            Import result with bytes_written and files_created

        Raises:
            ContainerNotFoundError: If container not found
            PathSecurityError: If path is invalid or tar tries to escape
            DockerAPIError: If Docker operations fail
            ValueError: If tar exceeds size limit
        """
        normalized_dest = self._validate_path(dest)
        container = self._get_container(container_id)

        try:
            # Collect tar data if streaming
            if stream:
                chunks = []
                total_size = 0
                max_bytes = max_size_mb * 1024 * 1024

                async for chunk in stream:
                    total_size += len(chunk)
                    if total_size > max_bytes:
                        raise ValueError(
                            f"Tar archive exceeds maximum size of {max_size_mb}MB"
                        )
                    chunks.append(chunk)

                tar_data = b"".join(chunks)

            if not tar_data:
                raise ValueError("No tar data provided")

            # Validate tar contents before extracting
            await self._validate_tar_contents(tar_data, normalized_dest)

            # Use Docker's put_archive API to extract tar data directly
            # This avoids command line length limits and is more efficient
            success = container.put_archive(normalized_dest, tar_data)

            if not success:
                raise DockerAPIError(
                    f"Failed to extract tar archive into {normalized_dest}"
                )

            # Count files created (approximate)
            count_cmd = f"find {shlex.quote(normalized_dest)} -type f | wc -l"
            count_result = container.exec_run(
                ["sh", "-c", count_cmd],
                user="1000:1000",
            )
            files_created = int(count_result.output.decode().strip())

            logger.info(
                f"Imported tar to {normalized_dest} in container {container_id}, "
                f"{len(tar_data)} bytes, ~{files_created} files"
            )

            return {
                "bytes_written": len(tar_data),
                "files_created": files_created,
                "dest_path": normalized_dest,
            }

        except APIError as e:
            raise DockerAPIError(f"Failed to import tar: {e}", e)

    async def _validate_tar_contents(self, tar_data: bytes, dest_path: str) -> None:
        """
        Validate tar contents to ensure they don't escape workspace.

        Args:
            tar_data: Tar archive data
            dest_path: Destination path

        Raises:
            PathSecurityError: If tar contains paths that would escape workspace
            ValueError: If tar is invalid
        """
        try:
            # Open tar in memory
            tar_buffer = io.BytesIO(tar_data)
            with tarfile.open(fileobj=tar_buffer, mode="r:*") as tar:
                for member in tar.getmembers():
                    # Check for absolute paths
                    if member.name.startswith("/"):
                        raise PathSecurityError(
                            member.name,
                            "Tar contains absolute paths"
                        )

                    # Check for parent directory references
                    if ".." in member.name.split("/"):
                        raise PathSecurityError(
                            member.name,
                            "Tar contains parent directory references"
                        )

                    # Compute final path and validate
                    final_path = posixpath.normpath(
                        posixpath.join(dest_path, member.name)
                    )
                    if not final_path.startswith(self.WORKSPACE_ROOT):
                        raise PathSecurityError(
                            member.name,
                            f"Tar would extract outside workspace: {final_path}"
                        )

                    # Check for suspicious file types
                    if member.issym() or member.islnk():
                        # Symlinks could potentially escape
                        logger.warning(
                            f"Tar contains symlink: {member.name}, "
                            f"extracting anyway"
                        )

        except tarfile.TarError as e:
            raise ValueError(f"Invalid tar archive: {e}")

    async def download_file(
        self, container_id: str, path: str
    ) -> tuple[bytes, FileInfo]:
        """
        Download a single file (convenience wrapper around read).

        Args:
            container_id: Container ID
            path: File path

        Returns:
            Tuple of (file content, file info)

        Raises:
            ContainerNotFoundError: If container not found
            FileNotFoundError: If file not found
            PathSecurityError: If path is invalid
            DockerAPIError: If Docker operations fail
        """
        # This is just an alias for read for now
        # Could be extended with range request support in the future
        return await self.read(container_id, path)
