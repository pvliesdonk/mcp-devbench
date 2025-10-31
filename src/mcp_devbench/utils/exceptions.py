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
