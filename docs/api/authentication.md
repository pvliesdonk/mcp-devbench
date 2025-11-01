# Authentication

MCP DevBench supports multiple authentication modes for different deployment scenarios.

## Authentication Modes

### None (Development Only)

No authentication required:

```bash
MCP_AUTH_MODE=none
```

**Use cases:**
- Local development
- Testing
- Trusted environments

⚠️ **WARNING:** Never use in production!

### Bearer Token

Simple token-based authentication:

```bash
MCP_AUTH_MODE=bearer
MCP_AUTH_BEARER_TOKEN=your-secret-token-here
```

**Client usage:**
```python
client = Client(
    ...,
    headers={"Authorization": "Bearer your-secret-token-here"}
)
```

**Best practices:**
- Use strong tokens (32+ bytes)
- Rotate regularly
- Store in secrets manager
- Use HTTPS in production

### OIDC (OpenID Connect)

OAuth 2.0 / OIDC authentication:

```bash
MCP_AUTH_MODE=oidc
MCP_OAUTH_CONFIG_URL=https://auth.example.com/.well-known/openid-configuration
MCP_OAUTH_CLIENT_ID=mcp-devbench
MCP_OAUTH_CLIENT_SECRET=client-secret
```

**Client usage:**
```python
# Get access token from OIDC provider
access_token = get_oidc_token(...)

# Use in client
client = Client(
    ...,
    headers={"Authorization": f"Bearer {access_token}"}
)
```

**Supported providers:**
- Auth0
- Okta
- Azure AD
- Google
- Keycloak
- Any OIDC-compliant provider

## HTTP Authentication

For HTTP transport mode, include authentication in headers:

```bash
curl -H "Authorization: Bearer your-token" \
  http://localhost:8000/api/tools/call
```

## Stdio Authentication

For stdio mode, authentication happens at process level:

```bash
# Run server with restricted permissions
sudo -u mcp-user python -m mcp_devbench.server
```

## Error Responses

**401 Unauthorized:**
```json
{
  "error": {
    "code": -32000,
    "message": "Authentication required"
  }
}
```

**403 Forbidden:**
```json
{
  "error": {
    "code": -32000,
    "message": "Insufficient permissions"
  }
}
```

## Next Steps

- **[API Overview](overview.md)** - API documentation
- **[Security Guide](../guide/security.md)** - Security best practices
