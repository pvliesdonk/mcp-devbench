# Configuration

MCP DevBench is configured entirely through environment variables. This guide covers all available configuration options.

## Configuration Files

MCP DevBench does not use configuration files. All settings are provided via environment variables, which can be set:

- Directly in your shell
- In a `.env` file (loaded automatically)
- In Docker Compose or Kubernetes manifests
- Through your CI/CD system

## Core Settings

### Transport Configuration

Control how MCP DevBench communicates with clients:

```bash
# Transport mode: stdio, sse, or streamable-http
MCP_TRANSPORT_MODE=stdio

# Host to bind to (HTTP/SSE modes only)
MCP_HOST=localhost

# Port to bind to (HTTP/SSE modes only)
MCP_PORT=8000
```

**Transport Modes:**

- `stdio` - Standard input/output (default, best for MCP clients)
- `sse` - Server-Sent Events over HTTP
- `streamable-http` - HTTP with streaming support

### Authentication

Configure authentication for your deployment:

```bash
# Authentication mode: none, bearer, or oidc
MCP_AUTH_MODE=none

# Bearer token (when MCP_AUTH_MODE=bearer)
MCP_AUTH_BEARER_TOKEN=your-secret-token

# OIDC configuration (when MCP_AUTH_MODE=oidc)
MCP_OAUTH_CONFIG_URL=https://your-oidc-provider/.well-known/openid-configuration
MCP_OAUTH_CLIENT_ID=your-client-id
MCP_OAUTH_CLIENT_SECRET=your-client-secret
```

**Authentication Modes:**

- `none` - No authentication (development only)
- `bearer` - Simple bearer token authentication
- `oidc` - OpenID Connect authentication

!!! warning
    Never use `none` authentication in production! Always use `bearer` or `oidc`.

### Database

Configure the database for persistent storage:

```bash
# Database connection URL
MCP_DATABASE_URL=sqlite:///mcp-devbench.db

# For PostgreSQL:
# MCP_DATABASE_URL=postgresql://user:pass@localhost/mcp_devbench

# Connection pool settings
MCP_DB_POOL_SIZE=5
MCP_DB_MAX_OVERFLOW=10
MCP_DB_POOL_TIMEOUT=30
```

### Docker Configuration

Configure Docker daemon connection:

```bash
# Docker daemon socket
MCP_DOCKER_HOST=unix:///var/run/docker.sock

# For remote Docker:
# MCP_DOCKER_HOST=tcp://docker-host:2376
# MCP_DOCKER_TLS_VERIFY=1
# MCP_DOCKER_CERT_PATH=/path/to/certs
```

## Security Settings

### Image Policy

Control which Docker images can be spawned:

```bash
# Allowed images (comma-separated)
MCP_ALLOWED_IMAGES=python:3.11-slim,node:18-slim,ubuntu:22.04

# Allow all images (DANGEROUS - dev only)
# MCP_ALLOWED_IMAGES=*
```

!!! danger
    Using `*` for allowed images is a security risk. Only do this in trusted development environments.

### Container Security

Configure container security policies:

```bash
# Default memory limit (MB)
MCP_CONTAINER_MEMORY_LIMIT=512

# Default CPU limit (cores)
MCP_CONTAINER_CPU_LIMIT=1.0

# Default PID limit
MCP_CONTAINER_PID_LIMIT=256

# Enable read-only root filesystem
MCP_CONTAINER_READ_ONLY_ROOTFS=true

# Drop all capabilities
MCP_CONTAINER_DROP_CAPABILITIES=true
```

### Execution Limits

Control command execution:

```bash
# Maximum concurrent executions per container
MCP_MAX_CONCURRENT_EXECS=4

# Default execution timeout (seconds)
MCP_DEFAULT_EXEC_TIMEOUT=300

# Maximum execution timeout (seconds)
MCP_MAX_EXEC_TIMEOUT=3600
```

### Filesystem Security

Configure filesystem operation security:

```bash
# Workspace directory in containers
MCP_WORKSPACE_PATH=/workspace

# Maximum file size (MB)
MCP_MAX_FILE_SIZE=100

# Enable path validation
MCP_VALIDATE_PATHS=true
```

## Operational Settings

### Logging

Configure logging behavior:

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
MCP_LOG_LEVEL=INFO

# Log format: json or text
MCP_LOG_FORMAT=json

# Enable audit logging
MCP_AUDIT_ENABLED=true

# Audit log file
MCP_AUDIT_LOG_FILE=/var/log/mcp-devbench/audit.log
```

### Metrics

Configure Prometheus metrics:

```bash
# Enable Prometheus metrics
MCP_METRICS_ENABLED=true

# Metrics endpoint port
MCP_METRICS_PORT=9090
```

### Container Pool

Configure the warm container pool:

```bash
# Enable warm container pool
MCP_WARM_POOL_ENABLED=true

# Warm pool size
MCP_WARM_POOL_SIZE=5

# Warm pool image
MCP_WARM_POOL_IMAGE=python:3.11-slim

# Pool refresh interval (seconds)
MCP_WARM_POOL_REFRESH_INTERVAL=300
```

### Cleanup

Configure automatic cleanup:

```bash
# Enable automatic cleanup
MCP_CLEANUP_ENABLED=true

# Cleanup interval (seconds)
MCP_CLEANUP_INTERVAL=300

# Default TTL for ephemeral containers (seconds)
MCP_DEFAULT_CONTAINER_TTL=3600

# Cleanup orphaned containers on startup
MCP_CLEANUP_ON_STARTUP=true
```

## Example Configurations

### Development

```bash
# .env for development
MCP_TRANSPORT_MODE=stdio
MCP_AUTH_MODE=none
MCP_DATABASE_URL=sqlite:///dev.db
MCP_DOCKER_HOST=unix:///var/run/docker.sock
MCP_ALLOWED_IMAGES=*
MCP_LOG_LEVEL=DEBUG
MCP_LOG_FORMAT=text
```

### Production (HTTP)

```bash
# .env for production
MCP_TRANSPORT_MODE=streamable-http
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_AUTH_MODE=oidc
MCP_OAUTH_CONFIG_URL=https://auth.example.com/.well-known/openid-configuration
MCP_OAUTH_CLIENT_ID=mcp-devbench
MCP_DATABASE_URL=postgresql://user:pass@db:5432/mcp_devbench
MCP_DOCKER_HOST=unix:///var/run/docker.sock
MCP_ALLOWED_IMAGES=python:3.11-slim,node:18-slim,ubuntu:22.04
MCP_LOG_LEVEL=INFO
MCP_LOG_FORMAT=json
MCP_METRICS_ENABLED=true
MCP_AUDIT_ENABLED=true
MCP_WARM_POOL_ENABLED=true
MCP_CLEANUP_ENABLED=true
```

### Docker Compose

```yaml
version: '3.8'

services:
  mcp-devbench:
    image: ghcr.io/pvliesdonk/mcp-devbench:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./data:/data
    ports:
      - "8000:8000"
      - "9090:9090"
    environment:
      MCP_TRANSPORT_MODE: streamable-http
      MCP_HOST: 0.0.0.0
      MCP_PORT: 8000
      MCP_AUTH_MODE: bearer
      MCP_AUTH_BEARER_TOKEN: ${BEARER_TOKEN}
      MCP_DATABASE_URL: sqlite:////data/mcp-devbench.db
      MCP_ALLOWED_IMAGES: python:3.11-slim,node:18-slim
      MCP_LOG_LEVEL: INFO
      MCP_LOG_FORMAT: json
      MCP_METRICS_ENABLED: "true"
      MCP_AUDIT_ENABLED: "true"
```

## Environment Variable Reference

For a complete list of all environment variables with their defaults and descriptions, refer to the configuration examples above and the [Security Guide](../guide/security.md) for security-related settings.

## Next Steps

- **[User Guide](../guide/containers.md)** - Learn how to use MCP DevBench
- **[Security Guide](../guide/security.md)** - Understand security implications
- **[Operations Guide](../operations/deployment.md)** - Deploy to production
