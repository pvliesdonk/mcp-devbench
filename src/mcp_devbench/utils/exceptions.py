"""Custom exceptions for MCP DevBench."""


class MCPDevBenchError(Exception):
    """Base exception for MCP DevBench errors."""

    pass


class ContainerError(MCPDevBenchError):
    """Base exception for container-related errors."""

    pass


class ContainerNotFoundError(ContainerError):
    """Exception raised when a container is not found."""

    def __init__(self, identifier: str) -> None:
        """
        Initialize ContainerNotFoundError.

        Args:
            identifier: Container ID or alias that was not found
        """
        self.identifier = identifier
        super().__init__(f"Container not found: {identifier}")


class ContainerAlreadyExistsError(ContainerError):
    """Exception raised when a container with the same alias already exists."""

    def __init__(self, alias: str) -> None:
        """
        Initialize ContainerAlreadyExistsError.

        Args:
            alias: Alias that already exists
        """
        self.alias = alias
        super().__init__(f"Container with alias '{alias}' already exists")


class DockerAPIError(MCPDevBenchError):
    """Exception raised when Docker API calls fail."""

    def __init__(self, message: str, original_error: Exception | None = None) -> None:
        """
        Initialize DockerAPIError.

        Args:
            message: Error message
            original_error: Original exception from Docker
        """
        self.original_error = original_error
        super().__init__(message)


class ImageNotFoundError(DockerAPIError):
    """Exception raised when a Docker image is not found."""

    def __init__(self, image: str, original_error: Exception | None = None) -> None:
        """
        Initialize ImageNotFoundError.

        Args:
            image: Image reference that was not found
            original_error: Original exception from Docker
        """
        self.image = image
        super().__init__(f"Docker image not found: {image}", original_error)


class ContainerExitedError(DockerAPIError):
    """Exception raised when a container exits unexpectedly."""

    def __init__(
        self, container_id: str, exit_code: int, original_error: Exception | None = None
    ) -> None:
        """
        Initialize ContainerExitedError.

        Args:
            container_id: Container ID that exited
            exit_code: Exit code of the container
            original_error: Original exception from Docker
        """
        self.container_id = container_id
        self.exit_code = exit_code
        super().__init__(
            f"Container {container_id} exited unexpectedly with code {exit_code}",
            original_error,
        )


class DockerDaemonUnreachableError(DockerAPIError):
    """Exception raised when Docker daemon is unreachable."""

    def __init__(self, message: str = "Docker daemon is unreachable") -> None:
        """
        Initialize DockerDaemonUnreachableError.

        Args:
            message: Error message
        """
        super().__init__(message)


class ExecError(MCPDevBenchError):
    """Base exception for exec-related errors."""

    pass


class ExecNotFoundError(ExecError):
    """Exception raised when an exec is not found."""

    def __init__(self, exec_id: str) -> None:
        """
        Initialize ExecNotFoundError.

        Args:
            exec_id: Exec ID that was not found
        """
        self.exec_id = exec_id
        super().__init__(f"Exec not found: {exec_id}")


class ExecTimeoutError(ExecError):
    """Exception raised when an exec times out."""

    def __init__(self, exec_id: str, timeout_s: int) -> None:
        """
        Initialize ExecTimeoutError.

        Args:
            exec_id: Exec ID that timed out
            timeout_s: Timeout in seconds
        """
        self.exec_id = exec_id
        self.timeout_s = timeout_s
        super().__init__(f"Exec {exec_id} timed out after {timeout_s} seconds")


class ExecAlreadyCompletedError(ExecError):
    """Exception raised when trying to operate on a completed exec."""

    def __init__(self, exec_id: str) -> None:
        """
        Initialize ExecAlreadyCompletedError.

        Args:
            exec_id: Exec ID that is already completed
        """
        self.exec_id = exec_id
        super().__init__(f"Exec {exec_id} is already completed")


class FilesystemError(MCPDevBenchError):
    """Base exception for filesystem-related errors."""

    pass


class FileNotFoundError(FilesystemError):
    """Exception raised when a file is not found."""

    def __init__(self, path: str) -> None:
        """
        Initialize FileNotFoundError.

        Args:
            path: Path that was not found
        """
        self.path = path
        super().__init__(f"File not found: {path}")


class PathSecurityError(FilesystemError):
    """Exception raised when a path violates security constraints."""

    def __init__(self, path: str, reason: str) -> None:
        """
        Initialize PathSecurityError.

        Args:
            path: Path that violates security
            reason: Reason for the violation
        """
        self.path = path
        self.reason = reason
        super().__init__(f"Path security violation for '{path}': {reason}")


class FileConflictError(FilesystemError):
    """Exception raised when file ETag doesn't match."""

    def __init__(self, path: str, expected_etag: str, actual_etag: str) -> None:
        """
        Initialize FileConflictError.

        Args:
            path: Path with conflict
            expected_etag: Expected ETag
            actual_etag: Actual ETag
        """
        self.path = path
        self.expected_etag = expected_etag
        self.actual_etag = actual_etag
        super().__init__(
            f"File conflict at '{path}': expected ETag '{expected_etag}', but found '{actual_etag}'"
        )


class ImagePolicyError(MCPDevBenchError):
    """Exception raised when image policy validation fails."""

    def __init__(self, message: str) -> None:
        """
        Initialize ImagePolicyError.

        Args:
            message: Error message describing policy violation
        """
        super().__init__(message)
