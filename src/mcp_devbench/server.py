"""MCP DevBench server implementation using FastMCP 2."""

import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastmcp import FastMCP
from pydantic import BaseModel

from mcp_devbench.config import get_settings
from mcp_devbench.managers.container_manager import ContainerManager
from mcp_devbench.managers.exec_manager import ExecManager
from mcp_devbench.managers.filesystem_manager import FilesystemManager
from mcp_devbench.managers.output_streamer import get_output_streamer
from mcp_devbench.mcp_tools import (
    AttachInput,
    AttachOutput,
    CancelInput,
    CancelOutput,
    ExecInput,
    ExecOutput,
    ExecPollInput,
    ExecPollOutput,
    ExecStreamMessage,
    FileDeleteInput,
    FileDeleteOutput,
    FileListInput,
    FileListOutput,
    FileReadInput,
    FileReadOutput,
    FileStatInput,
    FileStatOutput,
    FileWriteInput,
    FileWriteOutput,
    KillInput,
    KillOutput,
    SpawnInput,
    SpawnOutput,
)
from mcp_devbench.models.attachments import Attachment
from mcp_devbench.models.database import close_db, get_db_manager, init_db
from mcp_devbench.repositories.attachments import AttachmentRepository
from mcp_devbench.repositories.containers import ContainerRepository
from mcp_devbench.utils import get_logger, setup_logging
from mcp_devbench.utils.docker_client import close_docker_client, get_docker_client
from mcp_devbench.utils.exceptions import (
    ContainerNotFoundError,
    ExecNotFoundError,
    FileConflictError,
    PathSecurityError,
)


class HealthCheckResponse(BaseModel):
    """Health check response model."""

    status: str
    docker_connected: bool
    database_initialized: bool = True
    version: str = "0.1.0"


# Initialize FastMCP server
mcp = FastMCP("MCP DevBench")
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan():
    """Lifespan context manager for startup and shutdown tasks."""
    settings = get_settings()

    # Setup logging
    setup_logging(log_level=settings.log_level, log_format=settings.log_format)
    logger.info("Starting MCP DevBench server", extra={"version": "0.1.0"})

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize database", extra={"error": str(e)})
        raise

    # Initialize Docker client
    try:
        get_docker_client()
        logger.info("Docker client initialized successfully")
    except Exception as e:
        logger.error("Failed to initialize Docker client", extra={"error": str(e)})
        raise

    yield

    # Cleanup
    logger.info("Shutting down MCP DevBench server")
    await close_db()
    close_docker_client()
    logger.info("MCP DevBench server stopped")


# Set lifespan
mcp.lifespan_handler = lifespan


@mcp.tool()
async def health() -> HealthCheckResponse:
    """
    Health check endpoint to verify server status and Docker connectivity.

    Returns:
        HealthCheckResponse with status and Docker connection info
    """
    try:
        docker_client = get_docker_client()
        docker_client.ping()
        docker_connected = True
    except Exception as e:
        logger.warning("Docker health check failed", extra={"error": str(e)})
        docker_connected = False

    return HealthCheckResponse(
        status="healthy" if docker_connected else "degraded",
        docker_connected=docker_connected,
        database_initialized=True,
    )


# ========== Feature 4.1: MCP Tool Endpoints ==========


@mcp.tool()
async def spawn(input_data: SpawnInput) -> SpawnOutput:
    """
    Create and start a new container.

    Args:
        input_data: Spawn input with image, persistent flag, alias, and ttl

    Returns:
        SpawnOutput with container_id, alias, and status
    """
    logger.info(
        "Spawning container",
        extra={
            "image": input_data.image,
            "persistent": input_data.persistent,
            "alias": input_data.alias,
        },
    )

    try:
        manager = ContainerManager()

        # Create container
        container = await manager.create_container(
            image=input_data.image,
            alias=input_data.alias,
            persistent=input_data.persistent,
            ttl_s=input_data.ttl_s,
        )

        # Start container
        await manager.start_container(container.id)

        logger.info(
            "Container spawned successfully",
            extra={"container_id": container.id, "alias": container.alias},
        )

        return SpawnOutput(
            container_id=container.id,
            alias=container.alias,
            status="running",
        )

    except Exception as e:
        logger.error("Failed to spawn container", extra={"error": str(e)})
        raise


@mcp.tool()
async def attach(input_data: AttachInput) -> AttachOutput:
    """
    Attach a client to a container.

    Args:
        input_data: Attach input with target, client_name, and session_id

    Returns:
        AttachOutput with container_id, alias, and workspace roots
    """
    logger.info(
        "Attaching to container",
        extra={
            "target": input_data.target,
            "client_name": input_data.client_name,
            "session_id": input_data.session_id,
        },
    )

    db_manager = get_db_manager()

    # Get container by ID or alias
    async with db_manager.get_session() as session:
        container_repo = ContainerRepository(session)
        container = await container_repo.get_by_identifier(input_data.target)

        if not container:
            logger.warning("Container not found for attach", extra={"target": input_data.target})
            raise ContainerNotFoundError(input_data.target)

        # Save container_id and alias before leaving context
        container_id = container.id
        container_alias = container.alias

        # Create attachment
        attachment_repo = AttachmentRepository(session)

        attachment = Attachment(
            container_id=container_id,
            client_name=input_data.client_name,
            session_id=input_data.session_id,
            attached_at=datetime.now(timezone.utc),
        )
        await attachment_repo.create(attachment)

    logger.info(
        "Client attached successfully",
        extra={
            "container_id": container_id,
            "client_name": input_data.client_name,
        },
    )

    return AttachOutput(
        container_id=container_id,
        alias=container_alias,
        roots=[f"workspace:{container_id}"],
    )


@mcp.tool()
async def kill(input_data: KillInput) -> KillOutput:
    """
    Stop and remove a container.

    Args:
        input_data: Kill input with container_id and force flag

    Returns:
        KillOutput with status
    """
    logger.info(
        "Killing container",
        extra={"container_id": input_data.container_id, "force": input_data.force},
    )

    try:
        manager = ContainerManager()
        db_manager = get_db_manager()

        # Stop container
        await manager.stop_container(input_data.container_id, timeout=0 if input_data.force else 10)

        # Remove container
        await manager.remove_container(input_data.container_id, force=input_data.force)

        # Detach all active attachments
        async with db_manager.get_session() as session:
            attachment_repo = AttachmentRepository(session)
            await attachment_repo.detach_all_for_container(input_data.container_id)

        logger.info(
            "Container killed successfully",
            extra={"container_id": input_data.container_id},
        )

        return KillOutput(status="stopped")

    except Exception as e:
        logger.error("Failed to kill container", extra={"error": str(e)})
        raise


@mcp.tool()
async def exec_start(input_data: ExecInput) -> ExecOutput:
    """
    Start command execution in a container.

    Args:
        input_data: Exec input with container_id, cmd, and execution parameters

    Returns:
        ExecOutput with exec_id
    """
    logger.info(
        "Starting exec",
        extra={
            "container_id": input_data.container_id,
            "cmd": input_data.cmd,
            "as_root": input_data.as_root,
        },
    )

    try:
        manager = ExecManager()

        # Start execution
        exec_id = await manager.execute(
            container_id=input_data.container_id,
            cmd=input_data.cmd,
            cwd=input_data.cwd,
            env=input_data.env or {},
            as_root=input_data.as_root,
            timeout_s=input_data.timeout_s,
            idempotency_key=input_data.idempotency_key,
        )

        logger.info("Exec started successfully", extra={"exec_id": exec_id})

        return ExecOutput(exec_id=exec_id, status="running")

    except Exception as e:
        logger.error("Failed to start exec", extra={"error": str(e)})
        raise


@mcp.tool()
async def exec_cancel(input_data: CancelInput) -> CancelOutput:
    """
    Cancel a running execution.

    Args:
        input_data: Cancel input with exec_id

    Returns:
        CancelOutput with status
    """
    logger.info("Cancelling exec", extra={"exec_id": input_data.exec_id})

    try:
        manager = ExecManager()

        # Cancel execution
        await manager.cancel(input_data.exec_id)

        logger.info("Exec cancelled successfully", extra={"exec_id": input_data.exec_id})

        return CancelOutput(status="cancelled", exec_id=input_data.exec_id)

    except Exception as e:
        logger.error("Failed to cancel exec", extra={"error": str(e)})
        raise


@mcp.tool()
async def exec_poll(input_data: ExecPollInput) -> ExecPollOutput:
    """
    Poll for execution output and status.

    Args:
        input_data: Poll input with exec_id and after_seq

    Returns:
        ExecPollOutput with messages and completion status
    """
    logger.debug(
        "Polling exec",
        extra={"exec_id": input_data.exec_id, "after_seq": input_data.after_seq},
    )

    try:
        # Get streamed output messages
        streamer = get_output_streamer()

        # Poll for messages after the specified sequence
        stream_messages, is_complete = await streamer.poll(
            input_data.exec_id, after_seq=input_data.after_seq
        )

        # Convert to ExecStreamMessage objects
        messages = []
        for msg in stream_messages:
            # Check if it's a completion message
            if msg.get("complete", False):
                messages.append(
                    ExecStreamMessage(
                        seq=msg.get("seq", 0),
                        exit_code=msg.get("exit_code"),
                        usage=msg.get("usage"),
                        complete=True,
                    )
                )
            else:
                messages.append(
                    ExecStreamMessage(
                        seq=msg.get("seq", 0),
                        stream=msg.get("stream"),
                        data=msg.get("data"),
                        ts=msg.get("ts"),
                        complete=False,
                    )
                )

        return ExecPollOutput(messages=messages, complete=is_complete)

    except ExecNotFoundError:
        logger.warning("Exec not found for polling", extra={"exec_id": input_data.exec_id})
        raise
    except Exception as e:
        logger.error("Failed to poll exec", extra={"error": str(e)})
        raise


# ========== Feature 4.2: MCP Resource Implementation ==========


@mcp.tool()
async def fs_read(input_data: FileReadInput) -> FileReadOutput:
    """
    Read a file from container workspace.

    Args:
        input_data: File read input with container_id and path

    Returns:
        FileReadOutput with file content and metadata
    """
    logger.debug(
        "Reading file",
        extra={"container_id": input_data.container_id, "path": input_data.path},
    )

    try:
        manager = FilesystemManager()

        # Read file and get metadata in one call
        content, file_info = await manager.read(input_data.container_id, input_data.path)

        return FileReadOutput(
            content=content,
            etag=file_info.etag,
            size=file_info.size,
            mime_type=file_info.mime_type,
        )

    except PathSecurityError as e:
        logger.warning("Path security violation", extra={"error": str(e)})
        raise
    except Exception as e:
        logger.error("Failed to read file", extra={"error": str(e)})
        raise


@mcp.tool()
async def fs_write(input_data: FileWriteInput) -> FileWriteOutput:
    """
    Write a file to container workspace.

    Args:
        input_data: File write input with container_id, path, and content

    Returns:
        FileWriteOutput with path and new etag
    """
    logger.debug(
        "Writing file",
        extra={"container_id": input_data.container_id, "path": input_data.path},
    )

    try:
        manager = FilesystemManager()

        # Write file
        new_etag = await manager.write(
            input_data.container_id,
            input_data.path,
            input_data.content,
            if_match_etag=input_data.if_match_etag,
        )

        # Get file size
        file_info = await manager.stat(input_data.container_id, input_data.path)

        return FileWriteOutput(
            path=input_data.path,
            etag=new_etag,
            size=file_info.size,
        )

    except FileConflictError as e:
        logger.warning("File conflict during write", extra={"error": str(e)})
        raise
    except PathSecurityError as e:
        logger.warning("Path security violation", extra={"error": str(e)})
        raise
    except Exception as e:
        logger.error("Failed to write file", extra={"error": str(e)})
        raise


@mcp.tool()
async def fs_delete(input_data: FileDeleteInput) -> FileDeleteOutput:
    """
    Delete a file or directory from container workspace.

    Args:
        input_data: File delete input with container_id and path

    Returns:
        FileDeleteOutput with status
    """
    logger.debug(
        "Deleting file",
        extra={"container_id": input_data.container_id, "path": input_data.path},
    )

    try:
        manager = FilesystemManager()

        # Delete file/directory
        await manager.delete(input_data.container_id, input_data.path)

        return FileDeleteOutput(status="deleted", path=input_data.path)

    except PathSecurityError as e:
        logger.warning("Path security violation", extra={"error": str(e)})
        raise
    except Exception as e:
        logger.error("Failed to delete file", extra={"error": str(e)})
        raise


@mcp.tool()
async def fs_stat(input_data: FileStatInput) -> FileStatOutput:
    """
    Get file or directory metadata.

    Args:
        input_data: File stat input with container_id and path

    Returns:
        FileStatOutput with file metadata
    """
    logger.debug(
        "Getting file stat",
        extra={"container_id": input_data.container_id, "path": input_data.path},
    )

    try:
        manager = FilesystemManager()

        # Get file info
        file_info = await manager.stat(input_data.container_id, input_data.path)

        return FileStatOutput(
            path=file_info.path,
            size=file_info.size,
            is_dir=file_info.is_dir,
            permissions=file_info.permissions,
            mtime=file_info.mtime,
            etag=file_info.etag,
            mime_type=file_info.mime_type,
        )

    except PathSecurityError as e:
        logger.warning("Path security violation", extra={"error": str(e)})
        raise
    except Exception as e:
        logger.error("Failed to get file stat", extra={"error": str(e)})
        raise


@mcp.tool()
async def fs_list(input_data: FileListInput) -> FileListOutput:
    """
    List files and directories in a path.

    Args:
        input_data: File list input with container_id and path

    Returns:
        FileListOutput with directory entries
    """
    logger.debug(
        "Listing directory",
        extra={"container_id": input_data.container_id, "path": input_data.path},
    )

    try:
        manager = FilesystemManager()

        # List directory
        entries = await manager.list(input_data.container_id, input_data.path)

        # Convert FileInfo objects to FileStatOutput objects
        entry_outputs = [
            FileStatOutput(
                path=e.path,
                size=e.size,
                is_dir=e.is_dir,
                permissions=e.permissions,
                mtime=e.mtime,
                etag=e.etag,
                mime_type=e.mime_type,
            )
            for e in entries
        ]

        return FileListOutput(path=input_data.path, entries=entry_outputs)

    except PathSecurityError as e:
        logger.warning("Path security violation", extra={"error": str(e)})
        raise
    except Exception as e:
        logger.error("Failed to list directory", extra={"error": str(e)})
        raise


def main() -> None:
    """Main entry point for the MCP DevBench server."""
    settings = get_settings()

    logger.info(
        "Starting server",
        extra={
            "host": settings.host,
            "port": settings.port,
            "allowed_registries": settings.allowed_registries_list,
        },
    )

    try:
        # Run the FastMCP server with SSE transport for streamable HTTP
        mcp.run(transport="sse", host=settings.host, port=settings.port)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        sys.exit(0)
    except Exception as e:
        logger.error("Server error", extra={"error": str(e)})
        sys.exit(1)


if __name__ == "__main__":
    main()
