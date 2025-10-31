"""Filesystem manager for Docker container workspace operations."""

import base64
import hashlib
import json
import os
import posixpath
import shlex
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, List, Optional

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
            content: File content
            mtime: Optional modification time

        Returns:
            ETag string
        """
        hash_input = content
        if mtime:
            hash_input += mtime.encode()
        return hashlib.md5(hash_input).hexdigest()

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

            # Create parent directories
            parent_dir = posixpath.dirname(normalized_path)
            if parent_dir != self.WORKSPACE_ROOT:
                mkdir_cmd = f"mkdir -p {shlex.quote(parent_dir)}"
                container.exec_run(
                    ["sh", "-c", mkdir_cmd],
                    user="1000:1000"
                )

            # Write file using base64 encoding to handle binary content
            # This avoids issues with special characters and binary data
            content_b64 = base64.b64encode(content).decode('ascii')
            write_cmd = (
                f"echo {shlex.quote(content_b64)} | base64 -d > {shlex.quote(normalized_path)}"
            )
            exec_result = container.exec_run(
                ["sh", "-c", write_cmd],
                user="1000:1000"
            )

            if exec_result.exit_code != 0:
                raise DockerAPIError(
                    f"Failed to write file: {exec_result.output.decode()}"
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

            # For files, calculate etag
            etag = ""
            if not is_dir:
                # Read a small portion to calculate etag
                content, _ = await self.read(container_id, path)
                etag = self._calculate_etag(content, mtime_str)
            else:
                # For directories, use a simple hash
                etag = hashlib.md5(f"{normalized_path}:{mtime_str}".encode()).hexdigest()

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
                etag = hashlib.md5(
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
