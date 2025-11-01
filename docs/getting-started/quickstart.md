# Quick Start

This guide will help you get started with MCP DevBench in under 5 minutes.

## Start the Server

The fastest way to get started is using stdio mode:

```bash
uv run python -m mcp_devbench.server
```

For production use with HTTP transport:

```bash
export MCP_TRANSPORT_MODE=streamable-http
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
uv run python -m mcp_devbench.server
```

## Basic Workflow

MCP DevBench provides tools for managing Docker containers through the MCP protocol. Here's a typical workflow:

### 1. Spawn a Container

Create a new container from a Docker image:

```python
{
  "image": "python:3.11-slim",
  "persistent": false,
  "alias": "my-workspace"
}
```

This returns a `container_id` that you'll use for subsequent operations.

### 2. Attach to Container

Attach your client session to the container:

```python
{
  "target": "my-workspace",  # or use container_id
  "client_name": "claude",
  "session_id": "session-123"
}
```

### 3. Execute Commands

Run commands in the container:

```python
{
  "container_id": "c_abc123...",
  "cmd": ["python", "--version"],
  "timeout_s": 30
}
```

This returns an `exec_id` for polling results.

### 4. Poll for Output

Retrieve command output:

```python
{
  "exec_id": "e_xyz789...",
  "after_seq": 0
}
```

### 5. Filesystem Operations

**Write a file:**
```python
{
  "container_id": "c_abc123...",
  "path": "/workspace/hello.py",
  "content": "print('Hello, MCP DevBench!')"
}
```

**Read a file:**
```python
{
  "container_id": "c_abc123...",
  "path": "/workspace/hello.py"
}
```

**List directory:**
```python
{
  "container_id": "c_abc123...",
  "path": "/workspace"
}
```

### 6. Clean Up

Stop and remove the container:

```python
{
  "container_id": "c_abc123...",
  "force": true
}
```

## MCP Tools Overview

MCP DevBench provides the following tools:

| Tool | Purpose |
|------|---------|
| `spawn` | Create a new container |
| `attach` | Attach client to a container |
| `exec_start` | Start command execution |
| `exec_poll` | Poll for command output |
| `exec_signal` | Send signal to execution |
| `fs_read` | Read file contents |
| `fs_write` | Write file contents |
| `fs_delete` | Delete file or directory |
| `fs_list` | List directory contents |
| `kill` | Stop and remove container |
| `stats` | Get container statistics |
| `list` | List all containers |

For detailed documentation of each tool, see the [API Tools Reference](../api/tools.md).

## Example: Python Development Workflow

Here's a complete example of using MCP DevBench for Python development:

1. **Spawn a Python container:**
```python
spawn({
  "image": "python:3.11-slim",
  "alias": "python-dev"
})
```

2. **Attach to it:**
```python
attach({
  "target": "python-dev",
  "client_name": "claude",
  "session_id": "dev-session"
})
```

3. **Create a Python script:**
```python
fs_write({
  "container_id": "c_abc123...",
  "path": "/workspace/app.py",
  "content": """
def greet(name):
    return f"Hello, {name}!"

if __name__ == "__main__":
    print(greet("World"))
"""
})
```

4. **Run the script:**
```python
exec_start({
  "container_id": "c_abc123...",
  "cmd": ["python", "/workspace/app.py"],
  "timeout_s": 30
})
```

5. **Poll for output:**
```python
exec_poll({
  "exec_id": "e_xyz789...",
  "after_seq": 0
})
```

6. **Clean up:**
```python
kill({
  "container_id": "c_abc123...",
  "force": true
})
```

## Configuration

MCP DevBench is configured via environment variables. Here are the most important ones:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT_MODE` | `stdio` | Transport mode: `stdio`, `sse`, or `streamable-http` |
| `MCP_HOST` | `localhost` | Host to bind to (HTTP mode) |
| `MCP_PORT` | `8000` | Port to bind to (HTTP mode) |
| `MCP_AUTH_MODE` | `none` | Authentication mode: `none`, `bearer`, or `oidc` |
| `MCP_DATABASE_URL` | `sqlite:///mcp-devbench.db` | Database connection string |
| `MCP_DOCKER_HOST` | `unix:///var/run/docker.sock` | Docker daemon socket |

For a complete list of configuration options, see the [Configuration Guide](configuration.md).

## Next Steps

- **[User Guide](../guide/containers.md)** - Learn about container management
- **[API Reference](../api/overview.md)** - Detailed API documentation
- **[Security](../guide/security.md)** - Understand security features
- **[Operations](../operations/deployment.md)** - Deploy to production
