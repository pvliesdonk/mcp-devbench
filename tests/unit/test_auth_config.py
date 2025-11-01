"""Tests for authentication and transport configuration."""

from unittest.mock import MagicMock, patch

import pytest

from mcp_devbench.auth import create_auth_provider
from mcp_devbench.config.settings import Settings


class TestSettings:
    """Test configuration settings."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()
        assert settings.transport_mode == "streamable-http"
        assert settings.auth_mode == "none"
        assert settings.path == "/mcp"
        assert settings.bearer_token is None
        assert settings.oauth_client_id is None

    def test_transport_mode_configuration(self):
        """Test transport mode configuration."""
        # Test stdio
        settings = Settings(transport_mode="stdio")
        assert settings.transport_mode == "stdio"

        # Test sse
        settings = Settings(transport_mode="sse")
        assert settings.transport_mode == "sse"

        # Test streamable-http
        settings = Settings(transport_mode="streamable-http")
        assert settings.transport_mode == "streamable-http"

    def test_auth_mode_configuration(self):
        """Test authentication mode configuration."""
        # Test none
        settings = Settings(auth_mode="none")
        assert settings.auth_mode == "none"

        # Test bearer
        settings = Settings(auth_mode="bearer", bearer_token="test-token")
        assert settings.auth_mode == "bearer"
        assert settings.bearer_token == "test-token"

        # Test oauth
        settings = Settings(auth_mode="oauth")
        assert settings.auth_mode == "oauth"

        # Test oidc
        settings = Settings(auth_mode="oidc")
        assert settings.auth_mode == "oidc"

    def test_oauth_scopes_parsing(self):
        """Test OAuth required scopes parsing."""
        settings = Settings(oauth_required_scopes="read,write,admin")
        assert settings.oauth_required_scopes_list == ["read", "write", "admin"]

        # Test empty scopes
        settings = Settings(oauth_required_scopes="")
        assert settings.oauth_required_scopes_list == []

        # Test with spaces
        settings = Settings(oauth_required_scopes="read, write, admin")
        assert settings.oauth_required_scopes_list == ["read", "write", "admin"]


class TestAuthProvider:
    """Test authentication provider creation."""

    @patch("mcp_devbench.auth.get_settings")
    def test_no_auth(self, mock_get_settings):
        """Test no authentication."""
        mock_settings = MagicMock()
        mock_settings.auth_mode = "none"
        mock_get_settings.return_value = mock_settings

        auth = create_auth_provider()
        assert auth is None

    @patch("mcp_devbench.auth.get_settings")
    def test_bearer_auth(self, mock_get_settings):
        """Test bearer token authentication."""
        mock_settings = MagicMock()
        mock_settings.auth_mode = "bearer"
        mock_settings.bearer_token = "test-token-123"
        mock_get_settings.return_value = mock_settings

        auth = create_auth_provider()
        assert auth is not None
        # StaticTokenVerifier is created
        from fastmcp.server.auth import StaticTokenVerifier

        assert isinstance(auth, StaticTokenVerifier)

    @patch("mcp_devbench.auth.get_settings")
    def test_bearer_auth_missing_token(self, mock_get_settings):
        """Test bearer authentication without token raises error."""
        mock_settings = MagicMock()
        mock_settings.auth_mode = "bearer"
        mock_settings.bearer_token = None
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError, match="Bearer token authentication requires"):
            create_auth_provider()

    @patch("mcp_devbench.auth.get_settings")
    def test_oauth_not_implemented(self, mock_get_settings):
        """Test OAuth mode raises NotImplementedError."""
        mock_settings = MagicMock()
        mock_settings.auth_mode = "oauth"
        mock_get_settings.return_value = mock_settings

        with pytest.raises(NotImplementedError, match="OAuth mode requires manual"):
            create_auth_provider()

    @patch("mcp_devbench.auth.get_settings")
    @patch("fastmcp.server.auth.oidc_proxy.OIDCProxy.__init__")
    def test_oidc_auth(self, mock_oidc_init, mock_get_settings):
        """Test OIDC authentication."""
        mock_settings = MagicMock()
        mock_settings.auth_mode = "oidc"
        mock_settings.oauth_client_id = "client-id"
        mock_settings.oauth_client_secret = "client-secret"
        mock_settings.oauth_config_url = "https://example.com/.well-known/openid-configuration"
        mock_settings.oauth_base_url = "https://myserver.com"
        mock_settings.oauth_redirect_path = "/auth/callback"
        mock_settings.oauth_audience = None
        mock_settings.oauth_required_scopes_list = []
        mock_get_settings.return_value = mock_settings

        # Mock the __init__ to return None (normal behavior) without making HTTP calls
        mock_oidc_init.return_value = None

        create_auth_provider()
        # Verify OIDCProxy was instantiated with correct parameters
        mock_oidc_init.assert_called_once()
        call_kwargs = mock_oidc_init.call_args[1]
        assert call_kwargs["config_url"] == mock_settings.oauth_config_url
        assert call_kwargs["client_id"] == "client-id"
        assert call_kwargs["client_secret"] == "client-secret"
        assert call_kwargs["base_url"] == "https://myserver.com"
        assert call_kwargs["redirect_path"] == "/auth/callback"

    @patch("mcp_devbench.auth.get_settings")
    def test_oidc_missing_client_id(self, mock_get_settings):
        """Test OIDC without client_id raises error."""
        mock_settings = MagicMock()
        mock_settings.auth_mode = "oidc"
        mock_settings.oauth_client_id = None
        mock_settings.oauth_client_secret = "client-secret"
        mock_settings.oauth_config_url = "https://example.com/.well-known/openid-configuration"
        mock_settings.oauth_base_url = "https://myserver.com"
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError, match="OIDC authentication requires MCP_OAUTH_CLIENT_ID"):
            create_auth_provider()

    @patch("mcp_devbench.auth.get_settings")
    def test_oidc_missing_client_secret(self, mock_get_settings):
        """Test OIDC without client_secret raises error."""
        mock_settings = MagicMock()
        mock_settings.auth_mode = "oidc"
        mock_settings.oauth_client_id = "client-id"
        mock_settings.oauth_client_secret = None
        mock_settings.oauth_config_url = "https://example.com/.well-known/openid-configuration"
        mock_settings.oauth_base_url = "https://myserver.com"
        mock_get_settings.return_value = mock_settings

        with pytest.raises(
            ValueError, match="OIDC authentication requires MCP_OAUTH_CLIENT_SECRET"
        ):
            create_auth_provider()

    @patch("mcp_devbench.auth.get_settings")
    def test_oidc_missing_config_url(self, mock_get_settings):
        """Test OIDC without config_url raises error."""
        mock_settings = MagicMock()
        mock_settings.auth_mode = "oidc"
        mock_settings.oauth_client_id = "client-id"
        mock_settings.oauth_client_secret = "client-secret"
        mock_settings.oauth_config_url = None
        mock_settings.oauth_base_url = "https://myserver.com"
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError, match="OIDC authentication requires MCP_OAUTH_CONFIG_URL"):
            create_auth_provider()

    @patch("mcp_devbench.auth.get_settings")
    def test_oidc_missing_base_url(self, mock_get_settings):
        """Test OIDC without base_url raises error."""
        mock_settings = MagicMock()
        mock_settings.auth_mode = "oidc"
        mock_settings.oauth_client_id = "client-id"
        mock_settings.oauth_client_secret = "client-secret"
        mock_settings.oauth_config_url = "https://example.com/.well-known/openid-configuration"
        mock_settings.oauth_base_url = None
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError, match="OIDC authentication requires MCP_OAUTH_BASE_URL"):
            create_auth_provider()

    @patch("mcp_devbench.auth.get_settings")
    @patch("fastmcp.server.auth.oidc_proxy.OIDCProxy.__init__")
    def test_oidc_with_optional_params(self, mock_oidc_init, mock_get_settings):
        """Test OIDC with optional parameters."""
        mock_settings = MagicMock()
        mock_settings.auth_mode = "oidc"
        mock_settings.oauth_client_id = "client-id"
        mock_settings.oauth_client_secret = "client-secret"
        mock_settings.oauth_config_url = "https://example.com/.well-known/openid-configuration"
        mock_settings.oauth_base_url = "https://myserver.com"
        mock_settings.oauth_redirect_path = "/auth/callback"
        mock_settings.oauth_audience = "https://api.example.com"
        mock_settings.oauth_required_scopes_list = ["read", "write"]
        mock_get_settings.return_value = mock_settings

        # Mock the __init__ to return None (normal behavior) without making HTTP calls
        mock_oidc_init.return_value = None

        create_auth_provider()
        # Verify OIDCProxy was instantiated with correct parameters including optional ones
        mock_oidc_init.assert_called_once()
        call_kwargs = mock_oidc_init.call_args[1]
        assert call_kwargs["audience"] == "https://api.example.com"
        assert call_kwargs["required_scopes"] == ["read", "write"]

    @patch("mcp_devbench.auth.get_settings")
    def test_invalid_auth_mode(self, mock_get_settings):
        """Test invalid authentication mode raises error."""
        mock_settings = MagicMock()
        mock_settings.auth_mode = "invalid-mode"
        mock_get_settings.return_value = mock_settings

        with pytest.raises(ValueError, match="Invalid auth_mode"):
            create_auth_provider()
