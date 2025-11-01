"""Container lifecycle manager for Docker operations."""

from datetime import datetime
from typing import List
from uuid import uuid4

from docker import DockerClient
from docker.errors import APIError, NotFound
from docker.models.containers import Container as DockerContainer

from mcp_devbench.config import get_settings
from mcp_devbench.managers.image_policy_manager import get_image_policy_manager
from mcp_devbench.managers.security_manager import get_security_manager
from mcp_devbench.models.containers import Container
from mcp_devbench.models.database import get_db_manager
from mcp_devbench.repositories.containers import ContainerRepository
from mcp_devbench.utils import get_logger
from mcp_devbench.utils.docker_client import get_docker_client
from mcp_devbench.utils.exceptions import (
    ContainerAlreadyExistsError,
    ContainerNotFoundError,
    DockerAPIError,
)

logger = get_logger(__name__)


class ContainerManager:
    """Manager for Docker container lifecycle operations."""

    def __init__(self) -> None:
        """Initialize container manager."""
        self.settings = get_settings()
        self.docker_client: DockerClient = get_docker_client()
        self.db_manager = get_db_manager()
        self.image_policy = get_image_policy_manager()
        self.security = get_security_manager()

    async def create_container(
        self,
        image: str,
        alias: str | None = None,
        persistent: bool = False,
        ttl_s: int | None = None,
        idempotency_key: str | None = None,
    ) -> Container:
        """
        Create a new Docker container.

        Args:
            image: Docker image to use
            alias: Optional user-friendly alias
            persistent: Whether container is persistent
            ttl_s: Time to live in seconds for transient containers
            idempotency_key: Optional idempotency key to prevent duplicate creation

        Returns:
            Created container

        Raises:
            ContainerAlreadyExistsError: If alias already exists
            DockerAPIError: If Docker operations fail
            ImagePolicyError: If image is not allowed
        """
        # Check for existing container with same idempotency key
        if idempotency_key:
            async with self.db_manager.get_session() as session:
                repo = ContainerRepository(session)
                existing = await repo.get_by_idempotency_key(idempotency_key)

                if existing:
                    # Check if key is still valid (within 24 hours)
                    if existing.idempotency_key_created_at:
                        from datetime import timedelta, timezone

                        # Make sure the stored datetime is timezone-aware
                        key_created_at = existing.idempotency_key_created_at
                        if key_created_at.tzinfo is None:
                            key_created_at = key_created_at.replace(tzinfo=timezone.utc)

                        age = datetime.now(timezone.utc) - key_created_at
                        if age < timedelta(hours=24):
                            logger.info(
                                "Returning existing container for idempotency key",
                                extra={
                                    "idempotency_key": idempotency_key,
                                    "container_id": existing.id,
                                    "age_seconds": age.total_seconds(),
                                },
                            )
                            return existing

        # Validate and resolve image
        resolved = await self.image_policy.resolve_image(image)
        actual_image = resolved.resolved_ref

        # Generate opaque ID
        container_id = f"c_{uuid4()}"

        # Check if alias already exists
        if alias:
            async with self.db_manager.get_session() as session:
                repo = ContainerRepository(session)
                existing = await repo.get_by_alias(alias)
                if existing:
                    raise ContainerAlreadyExistsError(alias)

        try:
            # Prepare labels
            labels = {
                "com.mcp.devbench": "true",
                "com.mcp.container_id": container_id,
            }
            if alias:
                labels["com.mcp.alias"] = alias

            # Prepare volume configuration
            if persistent:
                volume_name = f"mcpdevbench_persist_{container_id}"
                volumes = {volume_name: {"bind": "/workspace", "mode": "rw"}}
            else:
                # Docker manages temporary volume with distinct naming
                volume_name = None
                volumes = {
                    f"mcpdevbench_transient_{container_id}": {"bind": "/workspace", "mode": "rw"}
                }

            # Get security configuration
            security_config = self.security.get_container_security_config(as_root=False)

            # Create Docker container with security controls
            docker_container: DockerContainer = self.docker_client.containers.create(
                image=actual_image,
                labels=labels,
                volumes=volumes,
                detach=True,
                tty=True,
                stdin_open=True,
                working_dir="/workspace",
                **security_config,
            )

            logger.info(
                "Docker container created",
                extra={
                    "container_id": container_id,
                    "docker_id": docker_container.id,
                    "image": image,
                    "resolved_image": actual_image,
                    "alias": alias,
                },
            )

            # Save to database
            from datetime import timezone

            now = datetime.now(timezone.utc)
            container = Container(
                id=container_id,
                docker_id=docker_container.id,
                alias=alias,
                image=actual_image,
                digest=resolved.digest,
                persistent=persistent,
                created_at=now,
                last_seen=now,
                ttl_s=ttl_s,
                volume_name=volume_name,
                status="stopped",  # Container is created but not started
                idempotency_key=idempotency_key,
                idempotency_key_created_at=now if idempotency_key else None,
            )

            async with self.db_manager.get_session() as session:
                repo = ContainerRepository(session)
                await repo.create(container)

            return container

        except APIError as e:
            logger.error("Docker API error creating container", extra={"error": str(e)})
            raise DockerAPIError(f"Failed to create container: {e}", e)

    async def start_container(self, container_id: str) -> None:
        """
        Start a Docker container.

        Args:
            container_id: Container ID

        Raises:
            ContainerNotFoundError: If container not found
            DockerAPIError: If Docker operations fail
        """
        # Get container from database
        async with self.db_manager.get_session() as session:
            repo = ContainerRepository(session)
            container = await repo.get(container_id)

            if not container:
                raise ContainerNotFoundError(container_id)

            try:
                # Get Docker container
                docker_container = self.docker_client.containers.get(container.docker_id)
                docker_container.start()

                logger.info(
                    "Docker container started",
                    extra={"container_id": container_id, "docker_id": container.docker_id},
                )

                # Update status
                await repo.update_status(container_id, "running")

            except NotFound:
                # Docker container doesn't exist, mark as error
                await repo.update_status(container_id, "error")
                raise ContainerNotFoundError(container_id)
            except APIError as e:
                logger.error("Docker API error starting container", extra={"error": str(e)})
                await repo.update_status(container_id, "error")
                raise DockerAPIError(f"Failed to start container: {e}", e)

    async def stop_container(self, container_id: str, timeout: int = 10) -> None:
        """
        Stop a Docker container gracefully.

        Args:
            container_id: Container ID
            timeout: Timeout in seconds before force-killing

        Raises:
            ContainerNotFoundError: If container not found
            DockerAPIError: If Docker operations fail
        """
        # Get container from database
        async with self.db_manager.get_session() as session:
            repo = ContainerRepository(session)
            container = await repo.get(container_id)

            if not container:
                raise ContainerNotFoundError(container_id)

            try:
                # Get Docker container
                docker_container = self.docker_client.containers.get(container.docker_id)
                docker_container.stop(timeout=timeout)

                logger.info(
                    "Docker container stopped",
                    extra={"container_id": container_id, "docker_id": container.docker_id},
                )

                # Update status
                await repo.update_status(container_id, "stopped")

            except NotFound:
                # Docker container doesn't exist, mark as stopped
                await repo.update_status(container_id, "stopped")
            except APIError as e:
                logger.error("Docker API error stopping container", extra={"error": str(e)})
                raise DockerAPIError(f"Failed to stop container: {e}", e)

    async def remove_container(self, container_id: str, force: bool = False) -> None:
        """
        Remove a Docker container and clean up resources.

        Args:
            container_id: Container ID
            force: Force remove even if running

        Raises:
            ContainerNotFoundError: If container not found
            DockerAPIError: If Docker operations fail
        """
        # Get container from database
        async with self.db_manager.get_session() as session:
            repo = ContainerRepository(session)
            container = await repo.get(container_id)

            if not container:
                raise ContainerNotFoundError(container_id)

            try:
                # Get Docker container
                docker_container = self.docker_client.containers.get(container.docker_id)
                docker_container.remove(force=force, v=not container.persistent)

                logger.info(
                    "Docker container removed",
                    extra={
                        "container_id": container_id,
                        "docker_id": container.docker_id,
                        "persistent": container.persistent,
                    },
                )

                # Remove persistent volume if specified
                if container.persistent and container.volume_name:
                    try:
                        volume = self.docker_client.volumes.get(container.volume_name)
                        volume.remove()
                        logger.info(
                            "Persistent volume removed",
                            extra={"volume_name": container.volume_name},
                        )
                    except NotFound:
                        pass  # Volume already removed
                    except APIError as e:
                        logger.warning(
                            "Failed to remove persistent volume",
                            extra={"volume_name": container.volume_name, "error": str(e)},
                        )

                # Remove from database
                await repo.delete(container)

            except NotFound:
                # Docker container doesn't exist, just remove from DB
                await repo.delete(container)
                logger.info(
                    "Container not found in Docker, removed from database",
                    extra={"container_id": container_id},
                )
            except APIError as e:
                logger.error("Docker API error removing container", extra={"error": str(e)})
                raise DockerAPIError(f"Failed to remove container: {e}", e)

    async def get_container(self, identifier: str) -> Container:
        """
        Get container by ID or alias.

        Args:
            identifier: Container ID or alias

        Returns:
            Container

        Raises:
            ContainerNotFoundError: If container not found
        """
        async with self.db_manager.get_session() as session:
            repo = ContainerRepository(session)
            container = await repo.get_by_identifier(identifier)

            if not container:
                raise ContainerNotFoundError(identifier)

            # Verify Docker container exists
            try:
                docker_container = self.docker_client.containers.get(container.docker_id)
                # Update status based on Docker state
                docker_status = docker_container.status
                if docker_status == "running" and container.status != "running":
                    await repo.update_status(container.id, "running")
                    container.status = "running"
                elif docker_status in ["exited", "stopped"] and container.status != "stopped":
                    await repo.update_status(container.id, "stopped")
                    container.status = "stopped"

            except NotFound:
                # Docker container doesn't exist
                await repo.update_status(container.id, "error")
                container.status = "error"

            return container

    async def list_containers(self, include_stopped: bool = False) -> List[Container]:
        """
        List all containers.

        Args:
            include_stopped: Include stopped containers

        Returns:
            List of containers
        """
        async with self.db_manager.get_session() as session:
            repo = ContainerRepository(session)
            return await repo.list_by_status(include_stopped=include_stopped)
