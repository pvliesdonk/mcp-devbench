# Deployment

Production deployment guide for MCP DevBench.

## Deployment Options

### Docker

```bash
docker run -d \
  --name mcp-devbench \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -p 8000:8000 \
  -e MCP_TRANSPORT_MODE=streamable-http \
  -e MCP_AUTH_MODE=bearer \
  -e MCP_AUTH_BEARER_TOKEN=${TOKEN} \
  ghcr.io/pvliesdonk/mcp-devbench:latest
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
      MCP_AUTH_MODE: oidc
      MCP_DATABASE_URL: sqlite:////data/mcp-devbench.db
    restart: unless-stopped
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: mcp-devbench
spec:
  replicas: 1
  selector:
    matchLabels:
      app: mcp-devbench
  template:
    metadata:
      labels:
        app: mcp-devbench
    spec:
      containers:
      - name: mcp-devbench
        image: ghcr.io/pvliesdonk/mcp-devbench:latest
        ports:
        - containerPort: 8000
        env:
        - name: MCP_TRANSPORT_MODE
          value: "streamable-http"
        volumeMounts:
        - name: docker-sock
          mountPath: /var/run/docker.sock
      volumes:
      - name: docker-sock
        hostPath:
          path: /var/run/docker.sock
```

## Production Configuration

```bash
# Transport
MCP_TRANSPORT_MODE=streamable-http
MCP_HOST=0.0.0.0
MCP_PORT=8000

# Authentication
MCP_AUTH_MODE=oidc
MCP_OAUTH_CONFIG_URL=https://auth.example.com/.well-known/openid-configuration

# Database
MCP_DATABASE_URL=postgresql://user:pass@db:5432/mcp_devbench

# Security
MCP_ALLOWED_IMAGES=python:3.11-slim,node:18-slim
MCP_CONTAINER_MEMORY_LIMIT=512
MCP_CONTAINER_CPU_LIMIT=1.0

# Observability
MCP_LOG_LEVEL=INFO
MCP_LOG_FORMAT=json
MCP_METRICS_ENABLED=true
MCP_AUDIT_ENABLED=true

# Features
MCP_WARM_POOL_ENABLED=true
MCP_CLEANUP_ENABLED=true
```

## Best Practices

1. **Use HTTPS** - Always use TLS in production
2. **Enable Authentication** - Never use `none` mode
3. **Set Resource Limits** - Prevent resource exhaustion
4. **Enable Monitoring** - Track metrics and logs
5. **Regular Backups** - Backup database and configs
6. **Keep Updated** - Update to latest versions
7. **Review Logs** - Monitor for security issues

## Next Steps

- **[Monitoring](monitoring.md)** - Set up observability
- **[Troubleshooting](troubleshooting.md)** - Debug issues
