"""Authentication provider factory for MCP DevBench."""

from typing import Any

from mcp_devbench.config import get_settings
from mcp_devbench.utils import get_logger

logger = get_logger(__name__)


def create_auth_provider() -> Any | None:
    """
    Create authentication provider based on configuration.

    Returns:
        Authentication provider instance or None for no authentication
    """
    settings = get_settings()

    if settings.auth_mode == "none":
        logger.info("No authentication configured")
        return None

    if settings.auth_mode == "bearer":
        if not settings.bearer_token:
            raise ValueError("Bearer token authentication requires MCP_BEARER_TOKEN to be set")

        # Use StaticTokenVerifier for simple bearer token authentication
        from fastmcp.server.auth import StaticTokenVerifier

        logger.info("Configuring bearer token authentication with StaticTokenVerifier")

        # StaticTokenVerifier expects a dict of token -> claims
        # For simple bearer auth, we just validate the token exists
        tokens = {settings.bearer_token: {"sub": "api-client", "scope": "api:full"}}
        return StaticTokenVerifier(tokens=tokens)

    if settings.auth_mode == "oauth":
        # Note: OAuth proxy requires manual configuration of provider endpoints
        # For full OAuth support, users should configure an OIDC provider instead
        logger.warning(
            "OAuth mode requires manual endpoint configuration. "
            "Consider using 'oidc' mode for automatic provider discovery."
        )
        raise NotImplementedError(
            "OAuth mode requires manual endpoint configuration. "
            "Use 'oidc' mode for providers with OIDC discovery support, "
            "or implement a custom OAuth provider."
        )

    if settings.auth_mode == "oidc":
        # Validate required OIDC configuration
        if not settings.oauth_client_id:
            raise ValueError("OIDC authentication requires MCP_OAUTH_CLIENT_ID to be set")
        if not settings.oauth_client_secret:
            raise ValueError("OIDC authentication requires MCP_OAUTH_CLIENT_SECRET to be set")
        if not settings.oauth_config_url:
            raise ValueError("OIDC authentication requires MCP_OAUTH_CONFIG_URL to be set")
        if not settings.oauth_base_url:
            raise ValueError("OIDC authentication requires MCP_OAUTH_BASE_URL to be set")

        from fastmcp.server.auth.oidc_proxy import OIDCProxy

        logger.info(
            "Configuring OIDC proxy authentication",
            extra={"config_url": settings.oauth_config_url},
        )

        # Build OIDC proxy configuration
        oidc_kwargs = {
            "config_url": settings.oauth_config_url,
            "client_id": settings.oauth_client_id,
            "client_secret": settings.oauth_client_secret,
            "base_url": settings.oauth_base_url,
            "redirect_path": settings.oauth_redirect_path,
        }

        # Add optional parameters if configured
        if settings.oauth_audience:
            oidc_kwargs["audience"] = settings.oauth_audience

        if settings.oauth_required_scopes_list:
            oidc_kwargs["required_scopes"] = settings.oauth_required_scopes_list

        return OIDCProxy(**oidc_kwargs)

    raise ValueError(f"Invalid auth_mode: {settings.auth_mode}")
