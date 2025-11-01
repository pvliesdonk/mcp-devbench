# MCP DevBench

[![CI](https://github.com/pvliesdonk/mcp-devbench/actions/workflows/ci.yml/badge.svg)](https://github.com/pvliesdonk/mcp-devbench/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/pvliesdonk/mcp-devbench/branch/main/graph/badge.svg)](https://codecov.io/gh/pvliesdonk/mcp-devbench)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

> **Production-ready Docker container management server implementing the Model Context Protocol (MCP)**

MCP DevBench provides isolated, persistent development workspaces through a secure, audited, and observable container management API. Built for AI assistants like Claude, it enables safe command execution and filesystem operations in Docker containers.

---

## ✨ Features

### Core Capabilities
- 🚀 **Container Lifecycle Management** - Create, start, stop, and remove Docker containers with fine-grained control
- 📁 **Secure Filesystem Operations** - Read, write, delete files with path validation and ETag-based concurrency control
- ⚡ **Async Command Execution** - Non-blocking execution with streaming output and timeout handling
- 🔐 **Enterprise Security** - Capability dropping, read-only rootfs, resource limits, and comprehensive audit logging
- 📊 **Production Observability** - Prometheus metrics, structured JSON logging, and system health monitoring

### Advanced Features
- **Warm Container Pool** - Sub-second container provisioning for instant attach
- **Graceful Shutdown** - Drain active operations before server termination
- **Automatic Recovery** - Reconciles Docker state with database on startup
- **Image Policy Enforcement** - Allow-list validation with digest pinning
- **Multi-Transport Support** - stdio, SSE, or HTTP-based MCP transports
- **Flexible Authentication** - None, Bearer token, or OIDC authentication modes

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker Engine
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

```bash
# Install uv
pip install uv

# Clone the repository
git clone https://github.com/pvliesdonk/mcp-devbench.git
cd mcp-devbench

# Install dependencies
uv sync
```

### Running the Server

**Development Mode (stdio)**
```bash
uv run python -m mcp_devbench.server
```

**Production Mode (HTTP)**
```bash
export MCP_TRANSPORT_MODE=streamable-http
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
uv run python -m mcp_devbench.server
```

**Using Docker**
```bash
docker build -t mcp-devbench .
docker run -v /var/run/docker.sock:/var/run/docker.sock \
  -p 8000:8000 \
  -e MCP_TRANSPORT_MODE=streamable-http \
  mcp-devbench
```

**Using Docker Compose**
```bash
docker-compose up -d
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   MCP DevBench API                   │
│           (FastMCP Server with Auth)                │
└─────────────────┬───────────────────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    │             │             │
    ▼             ▼             ▼
┌─────────┐  ┌─────────┐  ┌──────────┐
│Container│  │  Exec   │  │Filesystem│
│ Manager │  │ Manager │  │ Manager  │
└────┬────┘  └────┬────┘  └────┬─────┘
     │            │            │
     └────────────┼────────────┘
                  │
         ┌────────┼────────┐
         │        │        │
         ▼        ▼        ▼
    ┌────────┐ ┌────┐ ┌──────────┐
    │ Docker │ │ DB │ │  Audit   │
    │ Daemon │ │    │ │  Logger  │
    └────────┘ └────┘ └──────────┘
```

**Design Patterns:**
- **Repository Pattern** - Data access abstraction
- **Manager Pattern** - Business logic encapsulation
- **Dependency Injection** - Loose coupling via factory functions
- **Async/Await** - Non-blocking I/O throughout

---

## 📚 Usage Examples

### Basic Container Workflow

```python
from mcp_devbench.mcp_tools import *

# 1. Spawn a container
result = await spawn(SpawnInput(
    image="python:3.11-slim",
    persistent=False,
    alias="dev-workspace"
))
container_id = result.container_id

# 2. Attach to container
await attach(AttachInput(
    target=container_id,
    client_name="my-client",
    session_id="session-123"
))

# 3. Execute command
exec_result = await exec_start(ExecInput(
    container_id=container_id,
    cmd=["python", "--version"],
    timeout_s=30
))

# 4. Poll for output
output = await exec_poll(ExecPollInput(
    exec_id=exec_result.exec_id,
    after_seq=0
))

# 5. Write a file
await fs_write(FileWriteInput(
    container_id=container_id,
    path="/workspace/hello.py",
    content=b"print('Hello, World!')"
))

# 6. Clean up
await kill(KillInput(
    container_id=container_id,
    force=True
))
```

---

## ⚙️ Configuration

All configuration is managed through environment variables with the `MCP_` prefix.

### Essential Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT_MODE` | `streamable-http` | Transport: `stdio`, `sse`, or `streamable-http` |
| `MCP_HOST` | `0.0.0.0` | Server bind address (HTTP transports only) |
| `MCP_PORT` | `8000` | Server port (HTTP transports only) |
| `MCP_ALLOWED_REGISTRIES` | `docker.io,ghcr.io` | Comma-separated allowed registries |
| `MCP_LOG_LEVEL` | `INFO` | Logging level: DEBUG, INFO, WARNING, ERROR |
| `MCP_LOG_FORMAT` | `json` | Log format: `json` or `text` |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_AUTH_MODE` | `none` | Auth mode: `none`, `bearer`, or `oidc` |
| `MCP_BEARER_TOKEN` | - | Bearer token (when `auth_mode=bearer`) |
| `MCP_OAUTH_CLIENT_ID` | - | OIDC client ID |
| `MCP_OAUTH_CLIENT_SECRET` | - | OIDC client secret |
| `MCP_OAUTH_CONFIG_URL` | - | OIDC discovery URL |

### Advanced Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_STATE_DB` | `./state.db` | SQLite database path |
| `MCP_DRAIN_GRACE_S` | `60` | Shutdown grace period (seconds) |
| `MCP_TRANSIENT_GC_DAYS` | `7` | Transient container retention (days) |
| `MCP_WARM_POOL_ENABLED` | `true` | Enable warm container pool |
| `MCP_DEFAULT_IMAGE_ALIAS` | `python:3.11-slim` | Default warm pool image |

### Example Configurations

**Local Development (stdio)**
```bash
MCP_TRANSPORT_MODE=stdio
MCP_AUTH_MODE=none
MCP_LOG_LEVEL=DEBUG
MCP_LOG_FORMAT=text
```

**Production (HTTP + OIDC)**
```bash
MCP_TRANSPORT_MODE=streamable-http
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_AUTH_MODE=oidc
MCP_OAUTH_CLIENT_ID=your-client-id
MCP_OAUTH_CLIENT_SECRET=your-secret
MCP_OAUTH_CONFIG_URL=https://auth.example.com/.well-known/openid-configuration
MCP_LOG_LEVEL=INFO
MCP_LOG_FORMAT=json
```

---

## 🔧 MCP Tools Reference

### Container Management

#### `spawn`
Create and start a new container.

**Input:**
- `image` (string) - Docker image reference
- `persistent` (boolean) - Persist across restarts
- `alias` (string, optional) - User-friendly name
- `ttl_s` (integer, optional) - Time-to-live for transient containers

**Output:**
- `container_id` (string) - Opaque container ID
- `alias` (string) - Container alias
- `status` (string) - Container status

#### `attach`
Attach a client to a container for session tracking.

**Input:**
- `target` (string) - Container ID or alias
- `client_name` (string) - Client identifier
- `session_id` (string) - Session identifier

**Output:**
- `container_id` (string) - Actual container ID
- `alias` (string) - Container alias
- `roots` (array) - Workspace roots

#### `kill`
Stop and remove a container.

**Input:**
- `container_id` (string) - Container to remove
- `force` (boolean) - Force immediate removal

**Output:**
- `status` (string) - Operation status

### Command Execution

#### `exec_start`
Start command execution in a container.

**Input:**
- `container_id` (string) - Target container
- `cmd` (array) - Command and arguments
- `cwd` (string) - Working directory (default: `/workspace`)
- `env` (object) - Environment variables
- `as_root` (boolean) - Execute as root
- `timeout_s` (integer) - Execution timeout
- `idempotency_key` (string) - Prevent duplicate execution

**Output:**
- `exec_id` (string) - Execution ID
- `status` (string) - Initial status

#### `exec_cancel`
Cancel a running execution.

#### `exec_poll`
Poll for execution output and status.

**Input:**
- `exec_id` (string) - Execution ID
- `after_seq` (integer) - Return messages after sequence number

**Output:**
- `messages` (array) - Stream messages
- `complete` (boolean) - Execution complete flag

### Filesystem Operations

#### `fs_read`
Read a file from container workspace.

**Output includes:** content, etag, size, mime_type

#### `fs_write`
Write a file to container workspace.

**Supports:** ETag-based concurrency control via `if_match_etag`

#### `fs_delete`
Delete a file or directory.

#### `fs_stat`
Get file/directory metadata.

#### `fs_list`
List directory contents.

### System & Monitoring

#### `system_status`
Get system health and status.

**Output:**
- Docker connectivity status
- Active containers/attachments count
- Database status
- Server version

#### `metrics`
Retrieve Prometheus-formatted metrics.

#### `reconcile`
Manually trigger container reconciliation.

#### `garbage_collect`
Trigger manual garbage collection.

#### `list_containers` / `list_execs`
List all containers or active executions.

---

## 🔐 Security

### Built-in Security Features

- **Capability Dropping** - All Linux capabilities dropped by default
- **Read-Only Root Filesystem** - Prevents container modification
- **Resource Limits** - 512MB memory, 1 CPU, 256 PID limit per container
- **Path Validation** - Prevents directory traversal attacks
- **Image Allow-List** - Only approved registries allowed
- **Audit Logging** - Complete audit trail with PII redaction
- **User Isolation** - Configurable UID (default 1000)

### Security Best Practices

1. **Use OIDC Authentication** in production
2. **Restrict allowed registries** to trusted sources only
3. **Enable audit logging** and monitor for suspicious activity
4. **Run with least privilege** - never run as root
5. **Keep images updated** - use digest pinning for reproducibility
6. **Isolate network access** - use Docker network policies

---

## 📊 Observability

### Structured Logging

All operations are logged in JSON format with:
- ISO8601 timestamps
- Correlation IDs
- Contextual metadata
- Automatic PII redaction

### Prometheus Metrics

Available via the `metrics` tool:

- `mcp_devbench_container_spawns_total` - Container creation count
- `mcp_devbench_exec_total` - Command execution count
- `mcp_devbench_exec_duration_seconds` - Execution duration histogram
- `mcp_devbench_fs_operations_total` - Filesystem operation count
- `mcp_devbench_active_containers` - Active container gauge
- `mcp_devbench_memory_usage_bytes` - Container memory usage

### Audit Events

All operations generate audit events:
- `CONTAINER_SPAWN`, `CONTAINER_ATTACH`, `CONTAINER_KILL`
- `EXEC_START`, `EXEC_CANCEL`
- `FS_READ`, `FS_WRITE`, `FS_DELETE`
- `SYSTEM_RECONCILE`, `SYSTEM_GC`

---

## 🧪 Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=mcp_devbench --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_container_manager.py

# Run integration tests only
uv run pytest tests/integration/
```

### Code Quality

```bash
# Lint with ruff
uv run ruff check .

# Format code
uv run ruff format .

# Type checking (recommended)
uv run pyright src/
```

### Project Structure

```
mcp-devbench/
├── src/mcp_devbench/
│   ├── config/          # Configuration management
│   ├── models/          # SQLAlchemy ORM models
│   ├── managers/        # Business logic layer
│   ├── repositories/    # Data access layer
│   ├── utils/           # Utilities (logging, Docker, metrics)
│   ├── server.py        # FastMCP server
│   └── mcp_tools.py     # Pydantic models for MCP
├── tests/
│   ├── unit/            # Unit tests
│   └── integration/     # Integration tests
├── alembic/             # Database migrations
└── .github/workflows/   # CI/CD pipelines
```

---

## 📈 Project Status

**Current Version:** 0.1.0

### Completed Epics

✅ **Epic 1: Foundation Layer** - Configuration, state store, Docker lifecycle
✅ **Epic 2: Command Execution** - Async exec, streaming, idempotency
✅ **Epic 3: Filesystem Operations** - CRUD, batch ops, import/export
✅ **Epic 4: MCP Integration** - Tools, resources, streaming transport
✅ **Epic 5: Security** - Image policy, hardening, warm pool
✅ **Epic 6: State Management** - Shutdown, recovery, maintenance
✅ **Epic 7: Observability** - Audit logging, metrics, admin tools

**Test Coverage:** ~72% (201 tests)
**Code Quality:** Zero linting issues (ruff)
**Production Ready:** Yes, for small-to-medium deployments

### Roadmap

See [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) for detailed future plans.

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details on:
- Development workflow
- Testing guidelines
- Code style requirements
- Submission process

### Quick Contribution Steps

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run tests: `uv run pytest`
5. Lint code: `uv run ruff check .`
6. Commit with conventional commits: `git commit -m "feat: add amazing feature"`
7. Push and create a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🔗 Resources

- **Documentation:** [docs/](docs/)
- **Issue Tracker:** [GitHub Issues](https://github.com/pvliesdonk/mcp-devbench/issues)
- **Discussions:** [GitHub Discussions](https://github.com/pvliesdonk/mcp-devbench/discussions)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)

---

## 💬 Support

- **Questions?** Open a [Discussion](https://github.com/pvliesdonk/mcp-devbench/discussions)
- **Bug Reports:** File an [Issue](https://github.com/pvliesdonk/mcp-devbench/issues)
- **Security Issues:** See [SECURITY.md](SECURITY.md)

---

**Built with ❤️ using FastMCP, Docker, and modern Python async**
