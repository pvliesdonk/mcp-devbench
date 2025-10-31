"""Exec manager for running commands in containers."""

import asyncio
import time
from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from docker import DockerClient
from docker.errors import APIError, NotFound

from mcp_devbench.config import get_settings
from mcp_devbench.managers.output_streamer import get_output_streamer
from mcp_devbench.models.database import get_db_manager
from mcp_devbench.models.execs import Exec
from mcp_devbench.repositories.containers import ContainerRepository
from mcp_devbench.repositories.execs import ExecRepository
from mcp_devbench.utils import get_logger
from mcp_devbench.utils.docker_client import get_docker_client
from mcp_devbench.utils.exceptions import (
    ContainerNotFoundError,
    ExecNotFoundError,
)

logger = get_logger(__name__)


class ExecResult:
    """Result of a command execution."""

    def __init__(
        self,
        exec_id: str,
        exit_code: Optional[int],
        output: str,
        stderr: str = "",
        is_complete: bool = False,
        usage: Optional[Dict] = None,
    ):
        """
        Initialize ExecResult.
        
        Args:
            exec_id: Exec ID
            exit_code: Exit code (None if still running)
            output: Combined or stdout output
            stderr: Stderr output if separated
            is_complete: Whether exec has completed
            usage: Resource usage information
        """
        self.exec_id = exec_id
        self.exit_code = exit_code
        self.output = output
        self.stderr = stderr
        self.is_complete = is_complete
        self.usage = usage or {}


class ExecManager:
    """Manager for executing commands in Docker containers."""

    # Maximum concurrent executions per container
    MAX_CONCURRENT_EXECS = 4

    def __init__(self) -> None:
        """Initialize exec manager."""
        self.settings = get_settings()
        self.docker_client: DockerClient = get_docker_client()
        self.db_manager = get_db_manager()
        self.output_streamer = get_output_streamer()

        # Semaphores for limiting concurrent execs per container
        self._container_semaphores: Dict[str, asyncio.Semaphore] = {}

        # Track active execs
        self._active_execs: Dict[str, asyncio.Task] = {}

        # Idempotency key mapping (key -> exec_id) with 24hr TTL
        self._idempotency_keys: Dict[str, tuple[str, datetime]] = {}

        # Cancelled exec IDs
        self._cancelled: Dict[str, bool] = {}

    def _get_container_semaphore(self, container_id: str) -> asyncio.Semaphore:
        """
        Get or create semaphore for a container.
        
        Args:
            container_id: Container ID
            
        Returns:
            Semaphore for the container
        """
        if container_id not in self._container_semaphores:
            self._container_semaphores[container_id] = asyncio.Semaphore(
                self.MAX_CONCURRENT_EXECS
            )
        return self._container_semaphores[container_id]

    async def execute(
        self,
        container_id: str,
        cmd: List[str],
        cwd: str = "/workspace",
        env: Optional[Dict[str, str]] = None,
        as_root: bool = False,
        timeout_s: int = 600,
        idempotency_key: Optional[str] = None,
    ) -> str:
        """
        Execute a command in a container asynchronously.
        
        Args:
            container_id: Container ID
            cmd: Command and arguments to execute
            cwd: Working directory (default: /workspace)
            env: Environment variables
            as_root: Run as root user (UID 0) instead of default user (UID 1000)
            timeout_s: Timeout in seconds
            idempotency_key: Optional idempotency key to prevent duplicate execution
            
        Returns:
            Exec ID
            
        Raises:
            ContainerNotFoundError: If container not found
            DockerAPIError: If Docker operations fail
            ExecTimeoutError: If execution times out
        """
        # Check idempotency key
        if idempotency_key:
            if idempotency_key in self._idempotency_keys:
                existing_exec_id, created_at = self._idempotency_keys[idempotency_key]
                # Check if key is still valid (24hr TTL)
                age = (datetime.utcnow() - created_at).total_seconds()
                if age < 86400:  # 24 hours
                    logger.info(
                        "Returning existing exec for idempotency key",
                        extra={"idempotency_key": idempotency_key, "exec_id": existing_exec_id},
                    )
                    return existing_exec_id
                else:
                    # Key expired, remove it
                    del self._idempotency_keys[idempotency_key]

        # Generate exec ID
        exec_id = f"e_{uuid4()}"

        # Store idempotency key if provided
        if idempotency_key:
            self._idempotency_keys[idempotency_key] = (exec_id, datetime.utcnow())

        # Verify container exists
        async with self.db_manager.get_session() as session:
            container_repo = ContainerRepository(session)
            container = await container_repo.get(container_id)

            if not container:
                raise ContainerNotFoundError(container_id)

            # Create exec entry in database
            now = datetime.utcnow()
            exec_entry = Exec(
                exec_id=exec_id,
                container_id=container_id,
                cmd={"cmd": cmd, "cwd": cwd, "env": env or {}, "idempotency_key": idempotency_key},
                as_root=as_root,
                started_at=now,
            )

            exec_repo = ExecRepository(session)
            await exec_repo.create(exec_entry)

        # Execute command in background
        task = asyncio.create_task(
            self._execute_command(
                exec_id, container_id, cmd, cwd, env, as_root, timeout_s
            )
        )
        self._active_execs[exec_id] = task

        # Initialize output streaming
        await self.output_streamer.init_exec(exec_id)

        logger.info(
            "Exec started",
            extra={
                "exec_id": exec_id,
                "container_id": container_id,
                "cmd": cmd,
                "as_root": as_root,
            },
        )

        return exec_id

    async def _execute_command(
        self,
        exec_id: str,
        container_id: str,
        cmd: List[str],
        cwd: str,
        env: Optional[Dict[str, str]],
        as_root: bool,
        timeout_s: int,
    ) -> None:
        """
        Internal method to execute command and update database.
        
        Args:
            exec_id: Exec ID
            container_id: Container ID
            cmd: Command and arguments
            cwd: Working directory
            env: Environment variables
            as_root: Run as root
            timeout_s: Timeout in seconds
        """
        semaphore = self._get_container_semaphore(container_id)

        start_time = time.time()
        exit_code = None

        async with semaphore:
            try:
                # Get Docker container
                async with self.db_manager.get_session() as session:
                    container_repo = ContainerRepository(session)
                    container = await container_repo.get(container_id)

                    if not container:
                        logger.error("Container not found during exec", extra={"container_id": container_id})
                        return

                # Run Docker exec
                try:
                    docker_container = self.docker_client.containers.get(container.docker_id)

                    # Determine user
                    user = "0" if as_root else "1000"

                    # Create exec instance
                    exec_instance = docker_container.exec_run(
                        cmd=cmd,
                        workdir=cwd,
                        environment=env,
                        user=user,
                        demux=True,  # Separate stdout and stderr
                    )

                    # Get exit code and output
                    exit_code = exec_instance.exit_code
                    stdout_data = exec_instance.output[0] if exec_instance.output[0] else b""
                    stderr_data = exec_instance.output[1] if exec_instance.output[1] else b""

                    # Stream output chunks
                    if stdout_data:
                        await self.output_streamer.add_output(exec_id, "stdout", stdout_data)
                    if stderr_data:
                        await self.output_streamer.add_output(exec_id, "stderr", stderr_data)

                    # Decode output for logging
                    stdout = stdout_data.decode("utf-8", errors="replace")
                    stderr = stderr_data.decode("utf-8", errors="replace")

                    # Calculate wall time
                    wall_ms = int((time.time() - start_time) * 1000)

                    # Store resource usage
                    usage = {
                        "wall_ms": wall_ms,
                        "stdout_bytes": len(stdout_data),
                        "stderr_bytes": len(stderr_data),
                    }

                    logger.info(
                        "Exec completed",
                        extra={
                            "exec_id": exec_id,
                            "exit_code": exit_code,
                            "wall_ms": wall_ms,
                        },
                    )

                except NotFound:
                    logger.error("Docker container not found during exec", extra={"container_id": container_id})
                    exit_code = -1
                    usage = {"wall_ms": int((time.time() - start_time) * 1000)}

                except APIError as e:
                    logger.error("Docker API error during exec", extra={"error": str(e)})
                    exit_code = -1
                    usage = {"wall_ms": int((time.time() - start_time) * 1000)}

            except asyncio.TimeoutError:
                logger.warning("Exec timeout", extra={"exec_id": exec_id, "timeout_s": timeout_s})
                exit_code = -1
                usage = {"wall_ms": timeout_s * 1000, "timeout": True}

            finally:
                # Mark exec as complete in output streamer
                if exit_code is not None:
                    await self.output_streamer.complete(exec_id, exit_code, usage)

                # Update database with result
                async with self.db_manager.get_session() as session:
                    exec_repo = ExecRepository(session)
                    await exec_repo.complete_exec(exec_id, exit_code or -1, usage)

                # Remove from active execs
                if exec_id in self._active_execs:
                    del self._active_execs[exec_id]

    async def get_exec_result(self, exec_id: str) -> ExecResult:
        """
        Get the result of an execution.
        
        Args:
            exec_id: Exec ID
            
        Returns:
            ExecResult with status and output
            
        Raises:
            ExecNotFoundError: If exec not found
        """
        async with self.db_manager.get_session() as session:
            exec_repo = ExecRepository(session)
            exec_entry = await exec_repo.get(exec_id)

            if not exec_entry:
                raise ExecNotFoundError(exec_id)

            is_complete = exec_entry.ended_at is not None

            return ExecResult(
                exec_id=exec_id,
                exit_code=exec_entry.exit_code,
                output="",  # Output is now streamed via poll_output
                is_complete=is_complete,
                usage=exec_entry.usage,
            )

    async def poll_output(
        self, exec_id: str, after_seq: Optional[int] = None
    ) -> tuple[List[Dict], bool]:
        """
        Poll for output chunks after a given sequence number.
        
        Args:
            exec_id: Exec ID
            after_seq: Return chunks after this sequence (None for all)
            
        Returns:
            Tuple of (chunks, is_complete)
            
        Raises:
            ExecNotFoundError: If exec not found
        """
        # Verify exec exists
        async with self.db_manager.get_session() as session:
            exec_repo = ExecRepository(session)
            exec_entry = await exec_repo.get(exec_id)

            if not exec_entry:
                raise ExecNotFoundError(exec_id)

        # Poll from output streamer
        return await self.output_streamer.poll(exec_id, after_seq)

    async def get_active_execs(self, container_id: str) -> List[Exec]:
        """
        Get active execs for a container.
        
        Args:
            container_id: Container ID
            
        Returns:
            List of active execs
        """
        async with self.db_manager.get_session() as session:
            exec_repo = ExecRepository(session)
            return await exec_repo.get_active_by_container(container_id)

    async def cleanup_old_execs(self, hours: int = 24) -> int:
        """
        Clean up old completed execs and their output buffers.
        
        Args:
            hours: Age in hours
            
        Returns:
            Number of execs deleted
        """
        async with self.db_manager.get_session() as session:
            exec_repo = ExecRepository(session)
            old_execs = await exec_repo.get_old_completed(hours)

            count = 0
            for exec_entry in old_execs:
                # Clean up output buffers
                await self.output_streamer.cleanup(exec_entry.exec_id)

                # Delete from database
                await exec_repo.delete(exec_entry)
                count += 1

            logger.info("Cleaned up old execs", extra={"count": count, "hours": hours})
            return count

    async def cancel(self, exec_id: str) -> None:
        """
        Cancel a running execution.
        
        This will mark the exec as cancelled. Since docker-py exec_run is synchronous
        and doesn't support direct cancellation, we mark it as cancelled and it will
        be terminated when possible.
        
        Args:
            exec_id: Exec ID to cancel
            
        Raises:
            ExecNotFoundError: If exec not found
        """
        # Verify exec exists
        async with self.db_manager.get_session() as session:
            exec_repo = ExecRepository(session)
            exec_entry = await exec_repo.get(exec_id)

            if not exec_entry:
                raise ExecNotFoundError(exec_id)

        # Mark as cancelled
        self._cancelled[exec_id] = True

        # Cancel the task if it's still running
        if exec_id in self._active_execs:
            task = self._active_execs[exec_id]
            task.cancel()

            logger.info("Cancelled exec", extra={"exec_id": exec_id})

            # Add cancellation message to output stream
            await self.output_streamer.add_output(
                exec_id, "stderr", b"[CANCELLED]\n"
            )

        # Complete with exit code -2 for cancelled
        await self.output_streamer.complete(exec_id, -2, {"cancelled": True})

    async def cleanup_idempotency_keys(self, max_age_hours: int = 24) -> int:
        """
        Clean up expired idempotency keys.
        
        Args:
            max_age_hours: Maximum age in hours
            
        Returns:
            Number of keys deleted
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        keys_to_delete = []
        for key, (exec_id, created_at) in self._idempotency_keys.items():
            if created_at < cutoff:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._idempotency_keys[key]

        if keys_to_delete:
            logger.info(
                "Cleaned up expired idempotency keys",
                extra={"count": len(keys_to_delete)},
            )

        return len(keys_to_delete)
