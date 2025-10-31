"""Unit tests for ImagePolicyManager."""

import json
import os
from unittest.mock import MagicMock, Mock, patch

import pytest
from docker.errors import APIError, ImageNotFound

from mcp_devbench.managers.image_policy_manager import ImagePolicyManager, ResolvedImage
from mcp_devbench.utils.exceptions import ImagePolicyError


@pytest.fixture
def mock_docker_client():
    """Create a mock Docker client."""
    client = MagicMock()
    return client


@pytest.fixture
def image_policy_manager(mock_docker_client):
    """Create an ImagePolicyManager with mocked Docker client."""
    with patch("mcp_devbench.managers.image_policy_manager.get_docker_client") as mock_get_client:
        mock_get_client.return_value = mock_docker_client
        with patch("mcp_devbench.managers.image_policy_manager.get_settings") as mock_settings:
            settings = Mock()
            settings.allowed_registries_list = ["docker.io", "ghcr.io"]
            mock_settings.return_value = settings
            manager = ImagePolicyManager()
            yield manager


def test_extract_registry_default(image_policy_manager):
    """Test extracting registry from simple image reference."""
    assert image_policy_manager._extract_registry("python:3.11") == "docker.io"
    assert image_policy_manager._extract_registry("ubuntu") == "docker.io"


def test_extract_registry_explicit(image_policy_manager):
    """Test extracting registry from explicit registry reference."""
    assert image_policy_manager._extract_registry("docker.io/python:3.11") == "docker.io"
    assert image_policy_manager._extract_registry("ghcr.io/owner/repo:tag") == "ghcr.io"
    assert image_policy_manager._extract_registry("registry.example.com/image:tag") == "registry.example.com"
    assert image_policy_manager._extract_registry("localhost:5000/image:tag") == "localhost:5000"


def test_extract_registry_with_namespace(image_policy_manager):
    """Test extracting registry from image with namespace."""
    assert image_policy_manager._extract_registry("library/python:3.11") == "docker.io"
    assert image_policy_manager._extract_registry("myuser/myimage:latest") == "docker.io"


def test_validate_registry_allowed(image_policy_manager):
    """Test validating allowed registries."""
    # Should not raise for allowed registries
    image_policy_manager._validate_registry("docker.io")
    image_policy_manager._validate_registry("ghcr.io")


def test_validate_registry_denied(image_policy_manager):
    """Test denying disallowed registries."""
    with pytest.raises(ImagePolicyError) as exc_info:
        image_policy_manager._validate_registry("evil.registry.com")
    
    assert "not in allow-list" in str(exc_info.value)
    assert "evil.registry.com" in str(exc_info.value)


def test_normalize_image_ref_simple(image_policy_manager):
    """Test normalizing simple image references."""
    assert image_policy_manager._normalize_image_ref("python:3.11") == "docker.io/library/python:3.11"
    assert image_policy_manager._normalize_image_ref("ubuntu") == "docker.io/library/ubuntu"


def test_normalize_image_ref_with_namespace(image_policy_manager):
    """Test normalizing image references with namespace."""
    assert image_policy_manager._normalize_image_ref("myuser/myimage:tag") == "docker.io/myuser/myimage:tag"


def test_normalize_image_ref_explicit_registry(image_policy_manager):
    """Test normalizing image references with explicit registry."""
    assert image_policy_manager._normalize_image_ref("ghcr.io/owner/repo:tag") == "ghcr.io/owner/repo:tag"
    assert image_policy_manager._normalize_image_ref("registry.example.com/image:tag") == "registry.example.com/image:tag"


def test_validate_image_ref_valid(image_policy_manager):
    """Test validating valid image references."""
    assert image_policy_manager.validate_image_ref("python:3.11") is True
    assert image_policy_manager.validate_image_ref("ghcr.io/owner/repo:tag") is True


def test_validate_image_ref_invalid(image_policy_manager):
    """Test validating invalid image references."""
    assert image_policy_manager.validate_image_ref("evil.registry.com/image:tag") is False


@pytest.mark.asyncio
async def test_resolve_image_already_present(image_policy_manager, mock_docker_client):
    """Test resolving an image that's already present locally."""
    # Mock image already present
    mock_image = MagicMock()
    mock_docker_client.images.get.return_value = mock_image
    
    result = await image_policy_manager.resolve_image("python:3.11")
    
    assert isinstance(result, ResolvedImage)
    assert result.requested == "python:3.11"
    assert result.resolved_ref == "docker.io/library/python:3.11"
    assert result.registry == "docker.io"
    
    # Should check for image but not pull
    mock_docker_client.images.get.assert_called()
    mock_docker_client.images.pull.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_image_needs_pull(image_policy_manager, mock_docker_client):
    """Test resolving an image that needs to be pulled."""
    # Mock image not present, needs pull
    mock_docker_client.images.get.side_effect = ImageNotFound("not found")
    mock_docker_client.images.pull.return_value = None
    
    result = await image_policy_manager.resolve_image("python:3.11")
    
    assert isinstance(result, ResolvedImage)
    assert result.requested == "python:3.11"
    assert result.resolved_ref == "docker.io/library/python:3.11"
    
    # Should pull the image
    mock_docker_client.images.pull.assert_called_once()


@pytest.mark.asyncio
async def test_resolve_image_pull_failure(image_policy_manager, mock_docker_client):
    """Test resolving an image when pull fails."""
    # Mock image not present and pull fails
    mock_docker_client.images.get.side_effect = ImageNotFound("not found")
    mock_docker_client.images.pull.side_effect = APIError("pull failed")
    
    with pytest.raises(ImagePolicyError) as exc_info:
        await image_policy_manager.resolve_image("python:3.11")
    
    assert "Failed to pull image" in str(exc_info.value)


@pytest.mark.asyncio
async def test_resolve_image_disallowed_registry(image_policy_manager, mock_docker_client):
    """Test resolving an image from disallowed registry."""
    with pytest.raises(ImagePolicyError) as exc_info:
        await image_policy_manager.resolve_image("evil.registry.com/image:tag")
    
    assert "not in allow-list" in str(exc_info.value)


@pytest.mark.asyncio
async def test_resolve_image_with_digest(image_policy_manager, mock_docker_client):
    """Test resolving an image with digest pinning."""
    # Mock image present with digest
    mock_image = MagicMock()
    mock_image.attrs = {
        "RepoDigests": ["docker.io/library/python@sha256:abcd1234"]
    }
    mock_docker_client.images.get.return_value = mock_image
    
    result = await image_policy_manager.resolve_image("python:3.11", pin_digest=True)
    
    assert result.digest == "sha256:abcd1234"
    assert "@sha256:abcd1234" in result.resolved_ref


@pytest.mark.asyncio
async def test_get_image_digest(image_policy_manager, mock_docker_client):
    """Test getting image digest."""
    # Mock image with digest
    mock_image = MagicMock()
    mock_image.attrs = {
        "RepoDigests": ["docker.io/library/python@sha256:abcd1234"]
    }
    mock_docker_client.images.get.return_value = mock_image
    
    digest = await image_policy_manager._get_image_digest("python:3.11")
    
    assert digest == "sha256:abcd1234"


@pytest.mark.asyncio
async def test_get_image_digest_cache(image_policy_manager, mock_docker_client):
    """Test digest caching."""
    # Mock image with digest
    mock_image = MagicMock()
    mock_image.attrs = {
        "RepoDigests": ["docker.io/library/python@sha256:abcd1234"]
    }
    mock_docker_client.images.get.return_value = mock_image
    
    # First call
    digest1 = await image_policy_manager._get_image_digest("python:3.11")
    
    # Second call should use cache
    digest2 = await image_policy_manager._get_image_digest("python:3.11")
    
    assert digest1 == digest2
    # Should only call get once due to cache
    assert mock_docker_client.images.get.call_count == 1


@pytest.mark.asyncio
async def test_get_image_digest_no_digest(image_policy_manager, mock_docker_client):
    """Test getting digest when image has no digest."""
    # Mock image without digest
    mock_image = MagicMock()
    mock_image.attrs = {"RepoDigests": []}
    mock_docker_client.images.get.return_value = mock_image
    
    digest = await image_policy_manager._get_image_digest("python:3.11")
    
    assert digest is None


def test_clear_digest_cache(image_policy_manager):
    """Test clearing the digest cache."""
    # Add something to cache
    image_policy_manager._digest_cache["test:tag"] = "sha256:abc123"
    
    # Clear cache
    image_policy_manager.clear_digest_cache()
    
    assert len(image_policy_manager._digest_cache) == 0


def test_load_docker_auth_with_config(image_policy_manager):
    """Test loading Docker authentication from environment."""
    auth_config = {
        "auths": {
            "docker.io": {
                "auth": "dXNlcjpwYXNz"
            }
        }
    }
    
    with patch.dict(os.environ, {"MCP_DOCKER_CONFIG_JSON": json.dumps(auth_config)}):
        result = image_policy_manager._load_docker_auth()
    
    assert result is not None
    assert "docker.io" in result


def test_load_docker_auth_invalid_json(image_policy_manager):
    """Test loading Docker authentication with invalid JSON."""
    with patch.dict(os.environ, {"MCP_DOCKER_CONFIG_JSON": "invalid json"}):
        result = image_policy_manager._load_docker_auth()
    
    # Should return None on parse error
    assert result is None


def test_load_docker_auth_no_env(image_policy_manager):
    """Test loading Docker authentication when no env var set."""
    with patch.dict(os.environ, {}, clear=True):
        result = image_policy_manager._load_docker_auth()
    
    assert result is None
