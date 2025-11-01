"""MCP Tool implementations for container management."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Tool Input/Output Models for Feature 4.1


class SpawnInput(BaseModel):
    """Input model for spawn tool."""

    image: str = Field(..., description="Docker image reference")
    persistent: bool = Field(default=False, description="Whether container is persistent")
    alias: Optional[str] = Field(None, description="Optional user-friendly alias")
    ttl_s: Optional[int] = Field(None, description="Time to live in seconds for transient")


class SpawnOutput(BaseModel):
    """Output model for spawn tool."""

    container_id: str = Field(..., description="Opaque container ID (c_xxx)")
    alias: Optional[str] = Field(None, description="Container alias if provided")
    status: str = Field(..., description="Container status")


class AttachInput(BaseModel):
    """Input model for attach tool."""

    target: str = Field(..., description="Container ID or alias to attach to")
    client_name: str = Field(..., description="Name of the client attaching")
    session_id: str = Field(..., description="Unique session ID for this attachment")


class AttachOutput(BaseModel):
    """Output model for attach tool."""

    container_id: str = Field(..., description="Actual container ID")
    alias: Optional[str] = Field(None, description="Container alias if exists")
    roots: List[str] = Field(..., description="List of workspace roots (e.g., workspace:c_xxx)")


class KillInput(BaseModel):
    """Input model for kill tool."""

    container_id: str = Field(..., description="Container ID to stop and remove")
    force: bool = Field(default=False, description="Force removal without graceful stop")


class KillOutput(BaseModel):
    """Output model for kill tool."""

    status: str = Field(..., description="Status of the operation (stopped/removed)")


class ExecInput(BaseModel):
    """Input model for exec tool."""

    container_id: str = Field(..., description="Container ID to execute command in")
    cmd: List[str] = Field(..., description="Command and arguments to execute")
    cwd: str = Field(default="/workspace", description="Working directory")
    env: Optional[Dict[str, str]] = Field(None, description="Environment variables")
    as_root: bool = Field(default=False, description="Execute as root user")
    timeout_s: int = Field(default=600, description="Execution timeout in seconds")
    idempotency_key: Optional[str] = Field(
        None, description="Optional idempotency key to prevent duplicate execution"
    )


class ExecOutput(BaseModel):
    """Output model for exec tool."""

    exec_id: str = Field(..., description="Execution ID (e_xxx)")
    status: str = Field(default="running", description="Initial execution status")


class CancelInput(BaseModel):
    """Input model for cancel tool."""

    exec_id: str = Field(..., description="Execution ID to cancel")


class CancelOutput(BaseModel):
    """Output model for cancel tool."""

    status: str = Field(..., description="Cancellation status")
    exec_id: str = Field(..., description="Execution ID that was cancelled")


# Resource Models for Feature 4.2


class FileReadInput(BaseModel):
    """Input model for file read resource."""

    container_id: str = Field(..., description="Container ID")
    path: str = Field(..., description="Path to file within /workspace")


class FileReadOutput(BaseModel):
    """Output model for file read resource."""

    content: bytes = Field(..., description="File content")
    etag: str = Field(..., description="Entity tag for concurrency control")
    size: int = Field(..., description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type of the file")


class FileWriteInput(BaseModel):
    """Input model for file write resource."""

    container_id: str = Field(..., description="Container ID")
    path: str = Field(..., description="Path to file within /workspace")
    content: bytes = Field(..., description="File content to write")
    if_match_etag: Optional[str] = Field(None, description="Required etag for conditional write")


class FileWriteOutput(BaseModel):
    """Output model for file write resource."""

    path: str = Field(..., description="Path that was written")
    etag: str = Field(..., description="New entity tag")
    size: int = Field(..., description="File size in bytes")


class FileDeleteInput(BaseModel):
    """Input model for file delete resource."""

    container_id: str = Field(..., description="Container ID")
    path: str = Field(..., description="Path to file/directory to delete")


class FileDeleteOutput(BaseModel):
    """Output model for file delete resource."""

    status: str = Field(..., description="Deletion status")
    path: str = Field(..., description="Path that was deleted")


class FileStatInput(BaseModel):
    """Input model for file stat resource."""

    container_id: str = Field(..., description="Container ID")
    path: str = Field(..., description="Path to file/directory")


class FileStatOutput(BaseModel):
    """Output model for file stat resource."""

    path: str = Field(..., description="File path")
    size: int = Field(..., description="File size in bytes")
    is_dir: bool = Field(..., description="Whether path is a directory")
    permissions: str = Field(..., description="File permissions")
    mtime: datetime = Field(..., description="Last modification time")
    etag: str = Field(..., description="Entity tag")
    mime_type: Optional[str] = Field(None, description="MIME type if file")


class FileListInput(BaseModel):
    """Input model for file list resource."""

    container_id: str = Field(..., description="Container ID")
    path: str = Field(default="/workspace", description="Directory path to list")


class FileListOutput(BaseModel):
    """Output model for file list resource."""

    path: str = Field(..., description="Directory path")
    entries: List[FileStatOutput] = Field(..., description="List of file/directory entries")


# Streaming Models for Feature 4.3


class ExecPollInput(BaseModel):
    """Input model for exec polling."""

    exec_id: str = Field(..., description="Execution ID to poll")
    after_seq: int = Field(default=0, description="Return messages after this sequence number")


class ExecStreamMessage(BaseModel):
    """Output model for exec stream message."""

    seq: int = Field(..., description="Sequence number")
    stream: Optional[str] = Field(None, description="Stream type: stdout or stderr")
    data: Optional[str] = Field(None, description="Output data")
    ts: Optional[str] = Field(None, description="Timestamp")
    exit_code: Optional[int] = Field(None, description="Exit code if execution completed")
    usage: Optional[Dict[str, Any]] = Field(None, description="Resource usage if completed")
    complete: bool = Field(default=False, description="Whether execution is complete")


class ExecPollOutput(BaseModel):
    """Output model for exec polling."""

    messages: List[ExecStreamMessage] = Field(..., description="Stream messages")
    complete: bool = Field(..., description="Whether execution is complete")


# Admin and Monitoring Tools for Feature 7.2 and 7.3


class MetricsOutput(BaseModel):
    """Output model for metrics tool."""

    metrics: str = Field(..., description="Prometheus metrics in text format")


class SystemStatusOutput(BaseModel):
    """Output model for system status tool."""

    status: str = Field(..., description="Overall system status")
    docker_connected: bool = Field(..., description="Docker daemon connectivity")
    database_initialized: bool = Field(..., description="Database initialization status")
    active_containers: int = Field(..., description="Number of active containers")
    active_attachments: int = Field(..., description="Number of active attachments")
    version: str = Field(..., description="Server version")


class ReconcileInput(BaseModel):
    """Input model for reconcile tool."""

    force: bool = Field(default=False, description="Force reconciliation even if recently run")


class ReconcileOutput(BaseModel):
    """Output model for reconcile tool."""

    discovered: int = Field(..., description="Number of containers discovered")
    adopted: int = Field(..., description="Number of containers adopted into state")
    cleaned_up: int = Field(..., description="Number of containers cleaned up")
    orphaned: int = Field(..., description="Number of orphaned containers found")
    errors: int = Field(..., description="Number of errors encountered")


class GarbageCollectOutput(BaseModel):
    """Output model for garbage collection tool."""

    containers_removed: int = Field(..., description="Number of containers removed")
    execs_cleaned: int = Field(..., description="Number of exec records cleaned")
    attachments_cleaned: int = Field(..., description="Number of attachments cleaned")


class ContainerListOutput(BaseModel):
    """Output model for container list tool."""

    containers: List[Dict[str, Any]] = Field(..., description="List of container information")


class ExecListOutput(BaseModel):
    """Output model for exec list tool."""

    execs: List[Dict[str, Any]] = Field(..., description="List of active executions")
