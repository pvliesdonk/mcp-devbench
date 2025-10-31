"""Image policy and resolution manager."""

import asyncio
import json
from dataclasses import dataclass
from typing import Dict, Optional

from docker import DockerClient
from docker.errors import APIError, ImageNotFound

from mcp_devbench.config import get_settings
from mcp_devbench.utils import get_logger
from mcp_devbench.utils.docker_client import get_docker_client
from mcp_devbench.utils.exceptions import ImagePolicyError

logger = get_logger(__name__)


@dataclass
class ResolvedImage:
    """Resolved image information."""

    requested: str
    resolved_ref: str
    digest: Optional[str] = None
    registry: Optional[str] = None


class ImagePolicyManager:
    """Manager for image validation and resolution."""

    def __init__(self) -> None:
        """Initialize image policy manager."""
        self.settings = get_settings()
        self.docker_client: DockerClient = get_docker_client()
        self._allowed_registries = self.settings.allowed_registries_list
        self._digest_cache: Dict[str, str] = {}
        self._auth_config: Optional[Dict] = self._load_docker_auth()

    def _load_docker_auth(self) -> Optional[Dict]:
        """Load Docker authentication from configuration."""
        # Check for MCP_DOCKER_CONFIG_JSON environment variable
        import os

        docker_config_json = os.getenv("MCP_DOCKER_CONFIG_JSON")
        if docker_config_json:
            try:
                config = json.loads(docker_config_json)
                logger.info("Loaded Docker authentication configuration")
                return config.get("auths", {})
            except json.JSONDecodeError as e:
                logger.warning(
                    "Failed to parse MCP_DOCKER_CONFIG_JSON",
                    extra={"error": str(e)},
                )
        return None

    def _extract_registry(self, image_ref: str) -> str:
        """
        Extract registry from image reference.

        Args:
            image_ref: Image reference (e.g., "docker.io/python:3.11", "python:3.11")

        Returns:
            Registry host (e.g., "docker.io")
        """
        # If no slash, it's from docker.io (implicit)
        if "/" not in image_ref:
            return "docker.io"

        parts = image_ref.split("/")

        # Check if first part looks like a registry (has dots or port)
        if "." in parts[0] or ":" in parts[0]:
            return parts[0]

        # Otherwise, it's docker.io (implicit)
        return "docker.io"

    def _validate_registry(self, registry: str) -> None:
        """
        Validate registry against allow-list.

        Args:
            registry: Registry host to validate

        Raises:
            ImagePolicyError: If registry is not allowed
        """
        if registry not in self._allowed_registries:
            logger.warning(
                "Registry not in allow-list",
                extra={
                    "registry": registry,
                    "allowed_registries": self._allowed_registries,
                },
            )
            raise ImagePolicyError(
                f"Registry '{registry}' is not in allow-list. "
                f"Allowed registries: {', '.join(self._allowed_registries)}"
            )

    def _normalize_image_ref(self, image_ref: str) -> str:
        """
        Normalize image reference to include registry.

        Args:
            image_ref: Image reference

        Returns:
            Normalized image reference
        """
        # If no slash, add docker.io prefix
        if "/" not in image_ref:
            return f"docker.io/library/{image_ref}"

        # If no registry prefix, add docker.io
        parts = image_ref.split("/")
        if "." not in parts[0] and ":" not in parts[0]:
            return f"docker.io/{image_ref}"

        return image_ref

    async def resolve_image(
        self,
        requested: str,
        pin_digest: bool = False,
    ) -> ResolvedImage:
        """
        Resolve and validate an image reference.

        Args:
            requested: Requested image reference
            pin_digest: Whether to resolve to a specific digest

        Returns:
            Resolved image information

        Raises:
            ImagePolicyError: If image is not allowed or cannot be resolved
        """
        # Normalize the image reference
        normalized = self._normalize_image_ref(requested)

        # Extract and validate registry
        registry = self._extract_registry(normalized)
        self._validate_registry(registry)

        # Try to pull the image if not present
        try:
            await self._ensure_image_present(normalized)
        except Exception as e:
            logger.error(
                "Failed to pull image",
                extra={"image": normalized, "error": str(e)},
            )
            raise ImagePolicyError(f"Failed to pull image '{requested}': {e}")

        # Get digest if requested
        digest = None
        if pin_digest:
            digest = await self._get_image_digest(normalized)

        resolved_ref = normalized
        if digest:
            # Use digest reference if pinning
            base_ref = normalized.split(":")[0]
            resolved_ref = f"{base_ref}@{digest}"

        logger.info(
            "Image resolved",
            extra={
                "requested": requested,
                "resolved": resolved_ref,
                "digest": digest,
                "registry": registry,
            },
        )

        return ResolvedImage(
            requested=requested,
            resolved_ref=resolved_ref,
            digest=digest,
            registry=registry,
        )

    async def _ensure_image_present(self, image_ref: str) -> None:
        """
        Ensure image is present locally, pull if needed.

        Args:
            image_ref: Image reference to check/pull

        Raises:
            ImagePolicyError: If image cannot be pulled
        """
        try:
            # Check if image exists locally
            await asyncio.to_thread(self.docker_client.images.get, image_ref)
            logger.debug("Image already present locally", extra={"image": image_ref})
            return
        except ImageNotFound:
            # Need to pull the image
            logger.info("Pulling image", extra={"image": image_ref})

        try:
            # Pull the image with authentication if available
            auth_config = None
            if self._auth_config:
                registry = self._extract_registry(image_ref)
                auth_config = self._auth_config.get(registry)

            await asyncio.to_thread(
                self.docker_client.images.pull, image_ref, auth_config=auth_config
            )
            logger.info("Image pulled successfully", extra={"image": image_ref})

        except APIError as e:
            logger.error(
                "Failed to pull image",
                extra={"image": image_ref, "error": str(e)},
            )
            raise ImagePolicyError(f"Failed to pull image: {e}")

    async def _get_image_digest(self, image_ref: str) -> Optional[str]:
        """
        Get the digest for an image.

        Args:
            image_ref: Image reference

        Returns:
            Digest string or None if not available
        """
        # Check cache first
        if image_ref in self._digest_cache:
            return self._digest_cache[image_ref]

        try:
            image = await asyncio.to_thread(self.docker_client.images.get, image_ref)
            # Get the RepoDigests
            repo_digests = image.attrs.get("RepoDigests", [])
            if repo_digests:
                # Extract digest from first repo digest
                digest = repo_digests[0].split("@")[1]
                self._digest_cache[image_ref] = digest
                return digest

            logger.debug("No digest available for image", extra={"image": image_ref})
            return None

        except (ImageNotFound, APIError) as e:
            logger.warning(
                "Failed to get image digest",
                extra={"image": image_ref, "error": str(e)},
            )
            return None

    def validate_image_ref(self, image_ref: str) -> bool:
        """
        Validate an image reference without pulling.

        Args:
            image_ref: Image reference to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            normalized = self._normalize_image_ref(image_ref)
            registry = self._extract_registry(normalized)
            self._validate_registry(registry)
            return True
        except ImagePolicyError:
            return False

    def clear_digest_cache(self) -> None:
        """Clear the digest cache."""
        self._digest_cache.clear()
        logger.debug("Digest cache cleared")


# Singleton instance
_image_policy_manager: Optional[ImagePolicyManager] = None


def get_image_policy_manager() -> ImagePolicyManager:
    """Get the image policy manager singleton."""
    global _image_policy_manager
    if _image_policy_manager is None:
        _image_policy_manager = ImagePolicyManager()
    return _image_policy_manager
