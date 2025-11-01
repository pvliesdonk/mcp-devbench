# MCP DevBench

[![CI](https://github.com/pvliesdonk/mcp-devbench/actions/workflows/ci.yml/badge.svg)](https://github.com/pvliesdonk/mcp-devbench/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/pvliesdonk/mcp-devbench/branch/main/graph/badge.svg)](https://codecov.io/gh/pvliesdonk/mcp-devbench)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

MCP DevBench is a Docker container management server that implements the Model Context Protocol (MCP) for managing development environments. It provides isolated, persistent workspaces with secure command execution and filesystem operations.

## Features

- **Container Lifecycle Management**: Create, start, stop, and remove Docker containers
- **MCP Protocol Integration**: Full MCP server implementation with typed Pydantic models
- **State Management**: SQLite-based state persistence with SQLAlchemy
- **Configuration Management**: Environment-based configuration with Pydantic Settings
- **Structured Logging**: JSON-formatted logging for production observability
- **Docker Integration**: Secure Docker daemon communication with connection pooling
- **Audit Logging**: Complete audit trail for all operations with sensitive data redaction
- **Prometheus Metrics**: Built-in metrics collection for monitoring and alerting
- **Admin Tools**: System health status, container/exec listing, garbage collection, and reconciliation
- **Graceful Shutdown**: Drains active operations before shutdown
- **Automatic Recovery**: Reconciles Docker state with database on startup

## Requirements

- Python 3.11+
- Docker Engine
- uv package manager

## Quick Start

### Installation

1. Install uv if you haven't already:
```bash
pip install uv
```

2. Clone the repository:
```bash
git clone https://github.com/pvliesdonk/mcp-devbench.git
cd mcp-devbench
```

3. Install dependencies:
```bash
uv sync
```

### Running the Server

#### Development Mode
```bash
uv run python -m mcp_devbench.server
```

#### Using Docker Compose
```bash
docker-compose up -d
```

#### Using Docker
```bash
docker build -t mcp-devbench .
docker run -v /var/run/docker.sock:/var/run/docker.sock mcp-devbench
```

## Configuration

Configuration is managed through environment variables with the `MCP_` prefix:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_ALLOWED_REGISTRIES` | `docker.io,ghcr.io` | Comma-separated list of allowed Docker registries |
| `MCP_DOCKER_CONFIG_JSON` | (none) | Docker authentication config in JSON format |
| `MCP_STATE_DB` | `./state.db` | Path to SQLite state database |
| `MCP_DRAIN_GRACE_S` | `60` | Grace period in seconds for draining operations during shutdown |
| `MCP_TRANSIENT_GC_DAYS` | `7` | Days to keep transient containers before garbage collection |
| `MCP_DOCKER_HOST` | (auto-detect) | Docker daemon host URL |
| `MCP_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `MCP_LOG_FORMAT` | `json` | Log format (json or text) |
| `MCP_HOST` | `0.0.0.0` | Server host to bind to (for HTTP-based transports) |
| `MCP_PORT` | `8000` | Server port to bind to (for HTTP-based transports) |
| `MCP_DEFAULT_IMAGE_ALIAS` | `python:3.11-slim` | Default image for warm container pool |
| `MCP_WARM_POOL_ENABLED` | `true` | Enable warm container pool for fast attach |
| `MCP_WARM_HEALTH_CHECK_INTERVAL` | `60` | Interval in seconds for warm container health checks |

### Transport Configuration

MCP DevBench supports multiple transport modes:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT_MODE` | `streamable-http` | Transport protocol: `stdio`, `sse`, or `streamable-http` |
| `MCP_PATH` | `/mcp` | Path for HTTP-based transports (sse or streamable-http) |

**Transport Modes:**
- `stdio`: Standard input/output for local desktop clients (Claude Desktop, Cursor, etc.)
- `sse`: Server-Sent Events (legacy HTTP transport, use streamable-http instead)
- `streamable-http`: Recommended HTTP transport with full bidirectional streaming support

### Authentication Configuration

MCP DevBench supports multiple authentication modes for securing your server:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_AUTH_MODE` | `none` | Authentication mode: `none`, `bearer`, `oauth`, or `oidc` |
| `MCP_BEARER_TOKEN` | (none) | Bearer token for `bearer` authentication mode |
| `MCP_OAUTH_CLIENT_ID` | (none) | OAuth/OIDC client ID |
| `MCP_OAUTH_CLIENT_SECRET` | (none) | OAuth/OIDC client secret |
| `MCP_OAUTH_CONFIG_URL` | (none) | OIDC provider configuration URL (e.g., `https://auth.example.com/.well-known/openid-configuration`) |
| `MCP_OAUTH_BASE_URL` | (none) | Base URL of this server for OAuth callbacks |
| `MCP_OAUTH_REDIRECT_PATH` | `/auth/callback` | OAuth callback redirect path |
| `MCP_OAUTH_AUDIENCE` | (none) | OAuth audience parameter (required by some providers like Auth0) |
| `MCP_OAUTH_REQUIRED_SCOPES` | (empty) | Comma-separated list of required OAuth scopes |

**Authentication Modes:**

1. **none** (default): No authentication required
   ```bash
   MCP_AUTH_MODE=none
   ```

2. **bearer**: Simple bearer token authentication for API keys and service accounts
   ```bash
   MCP_AUTH_MODE=bearer
   MCP_BEARER_TOKEN=your-secret-token-here
   ```

3. **oidc**: OpenID Connect authentication with automatic provider discovery
   ```bash
   MCP_AUTH_MODE=oidc
   MCP_OAUTH_CLIENT_ID=your-client-id
   MCP_OAUTH_CLIENT_SECRET=your-client-secret
   MCP_OAUTH_CONFIG_URL=https://your-provider.com/.well-known/openid-configuration
   MCP_OAUTH_BASE_URL=https://your-server.com
   MCP_OAUTH_REDIRECT_PATH=/auth/callback
   # Optional:
   MCP_OAUTH_AUDIENCE=https://api.your-server.com
   MCP_OAUTH_REQUIRED_SCOPES=read,write,admin
   ```

4. **oauth**: Not directly supported - use `oidc` mode instead for OAuth providers with OIDC discovery support

**OIDC Provider Examples:**

- **Auth0**: Use `https://YOUR_DOMAIN.auth0.com/.well-known/openid-configuration`
- **Google**: Use `https://accounts.google.com/.well-known/openid-configuration`
- **Azure AD**: Use `https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0/.well-known/openid-configuration`
- **Keycloak**: Use `https://YOUR_KEYCLOAK_DOMAIN/realms/YOUR_REALM/.well-known/openid-configuration`

### Example .env file

**Basic configuration (no auth, HTTP transport):**
```bash
MCP_ALLOWED_REGISTRIES=docker.io,ghcr.io,registry.example.com
MCP_STATE_DB=/data/state.db
MCP_LOG_LEVEL=DEBUG
MCP_LOG_FORMAT=json
MCP_DEFAULT_IMAGE_ALIAS=python:3.11-slim
MCP_WARM_POOL_ENABLED=true
MCP_TRANSPORT_MODE=streamable-http
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_PATH=/mcp
```

**With bearer token authentication:**
```bash
MCP_TRANSPORT_MODE=streamable-http
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_AUTH_MODE=bearer
MCP_BEARER_TOKEN=my-secret-api-key-12345
```

**With OIDC authentication (Auth0 example):**
```bash
MCP_TRANSPORT_MODE=streamable-http
MCP_HOST=0.0.0.0
MCP_PORT=8000
MCP_AUTH_MODE=oidc
MCP_OAUTH_CLIENT_ID=your-auth0-client-id
MCP_OAUTH_CLIENT_SECRET=your-auth0-client-secret
MCP_OAUTH_CONFIG_URL=https://your-tenant.auth0.com/.well-known/openid-configuration
MCP_OAUTH_BASE_URL=https://your-mcp-server.com
MCP_OAUTH_AUDIENCE=https://your-mcp-server.com/api
MCP_OAUTH_REQUIRED_SCOPES=openid,profile,email
```

**STDIO transport for local use (e.g., Claude Desktop):**
```bash
MCP_TRANSPORT_MODE=stdio
MCP_AUTH_MODE=none
# Host and port are not used for stdio transport
```

## Development

### Running Tests
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=mcp_devbench --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_config.py
```

### Linting and Formatting
```bash
# Run ruff linter
uv run ruff check .

# Run ruff formatter
uv run ruff format .
```

## Architecture

```
src/mcp_devbench/
├── config/          # Configuration management
├── models/          # SQLAlchemy models
├── managers/        # Business logic managers (Docker, Exec, FS)
├── repositories/    # Database repositories
├── utils/           # Utility modules (logging, Docker client)
└── server.py        # FastMCP server implementation
```

## Project Status

This project has completed **Epic 1: Foundation Layer**, **Epic 2: Command Execution Engine**, **Epic 3: Filesystem Operations**, **Epic 4: MCP Protocol Integration**, **Epic 5: Image & Security Management**, and **Epic 6: State Management & Recovery**:

### Epic 1: Foundation Layer ✅
- [x] Feature 1.1: Project Scaffold & Configuration
- [x] Feature 1.2: State Store & Schema
- [x] Feature 1.3: Docker Container Lifecycle Manager

### Epic 2: Command Execution Engine ✅
- [x] Feature 2.1: Async Exec Core
  - ExecManager with docker-py integration
  - Parallel execution with semaphore-based limiting (4 concurrent per container)
  - Resource tracking and timeout handling
  - Root/non-root user support with security validation

- [x] Feature 2.2: Output Streaming with MCP poll-based streaming
  - OutputStreamer with bounded ring buffers (64MB default)
  - Sequence-numbered chunks for ordered delivery
  - Cursor-based polling mechanism
  - Backpressure handling with memory limits

- [x] Feature 2.3: Exec Cancellation & Idempotency
  - Task cancellation support
  - Idempotency keys with 24-hour TTL
  - Automatic cleanup of old executions
  - Cleanup of expired idempotency keys

### Epic 3: Filesystem Operations ✅
- [x] Feature 3.1: Basic Filesystem Operations
  - FilesystemManager for workspace operations
  - Read, write, delete, stat, and list operations
  - Path security validation (prevents escape from /workspace)
  - ETag implementation for concurrency control
  - Binary and text file support

- [x] Feature 3.2: Batch Operations
  - Atomic batch filesystem operations
  - Transaction support with rollback
  - Optimized performance for multiple operations
  - Conflict detection and resolution

- [x] Feature 3.3: Import/Export Operations
  - Tar-based bulk import/export
  - Streaming support for large archives
  - Glob pattern filtering
  - Compression support

### Epic 4: MCP Protocol Integration ✅
- [x] Feature 4.1: MCP Tool Endpoints
  - `spawn` - Create and start containers with image, alias, and persistence options
  - `attach` - Attach clients to containers with session tracking
  - `kill` - Stop and remove containers with graceful/force options
  - `exec_start` - Start command execution with environment, timeout, and idempotency
  - `exec_cancel` - Cancel running executions
  - `exec_poll` - Poll for execution output and status
  - Typed Pydantic models for all inputs/outputs
  - Comprehensive error handling and validation

- [x] Feature 4.2: MCP Resource Implementation
  - `fs_read` - Read files from workspace with metadata
  - `fs_write` - Write files with ETag-based concurrency control
  - `fs_delete` - Delete files and directories
  - `fs_stat` - Get file/directory metadata
  - `fs_list` - List directory contents
  - Access control validation
  - Binary content support

- [x] Feature 4.3: Streaming & Poll Transport
  - Cursor-based polling for exec output
  - Sequence-numbered stream messages
  - Completion status tracking
  - Connection and backpressure management

### Epic 5: Image & Security Management ✅
- [x] Feature 5.1: Image Allow-List & Resolution
  - ImagePolicyManager with registry validation
  - Image reference normalization and resolution
  - Optional digest pinning for reproducible builds
  - Docker authentication support via MCP_DOCKER_CONFIG_JSON
  - Automatic image pulling with caching
  - Clear policy violation error messages

- [x] Feature 5.2: Security Controls
  - Container hardening (drop ALL capabilities, read-only root filesystem)
  - User management (default UID 1000, as_root validation)
  - Resource limits (512MB memory, 1 CPU, 256 PIDs)
  - Security audit logging for privilege escalations
  - Never allow privileged mode
  - Network mode control

- [x] Feature 5.3: Warm Container Pool
  - Pre-warmed container for fast attach (<1s)
  - Automatic health checks every 60 seconds
  - Atomic claim with automatic recreation
  - Workspace cleanup between uses
  - Configurable via MCP_WARM_POOL_ENABLED

### Epic 6: State Management & Recovery ✅
- [x] Feature 6.1: Graceful Shutdown
  - ShutdownCoordinator for handling SIGTERM/SIGINT
  - Drains active operations with configurable grace period (MCP_DRAIN_GRACE_S)
  - Stops transient containers while preserving persistent ones
  - Ensures state is flushed to disk
  - Integrated into server lifespan

- [x] Feature 6.2: Boot Recovery & Reconciliation
  - ReconciliationManager for container discovery and adoption
  - Discovers containers with com.mcp.devbench label on startup
  - Adopts running containers not in database
  - Cleans up orphaned transient containers based on MCP_TRANSIENT_GC_DAYS
  - `reconcile` tool for manual reconciliation
  - Handles Docker daemon restarts gracefully

- [x] Feature 6.3: Background Maintenance
  - MaintenanceManager for periodic tasks
  - Hourly garbage collection of old transients
  - Cleanup of completed execs older than 24h
  - Periodic state sync with Docker
  - Database vacuuming for optimization
  - Health monitoring and metrics collection

### Epic 7: Observability & Operations ✅
- [x] Feature 7.1: Structured Audit Logging
  - AuditLogger with JSON structured logging for all operations
  - Complete audit trail for container, exec, filesystem, security, and transfer events
  - Automatic sensitive data redaction (passwords, tokens, keys, secrets)
  - ISO8601 timestamps and correlation IDs
  - Configurable detail level
  - 17 unit tests covering audit functionality

- [x] Feature 7.2: Metrics & Monitoring
  - Prometheus metrics collection via MetricsCollector
  - Counter metrics: container_spawns_total, exec_total, fs_operations_total
  - Histogram metrics: exec_duration_seconds, output_bytes
  - Gauge metrics: active_containers, active_attachments, memory_usage_bytes
  - `metrics` tool to expose Prometheus-formatted metrics
  - 14 unit tests covering metrics collection

- [x] Feature 7.3: Debug & Admin Tools
  - `system_status` tool for overall system health
  - `list_containers` tool for detailed container information
  - `list_execs` tool for active execution listing
  - `garbage_collect` tool for manual cleanup
  - `reconcile` tool with audit logging (from Epic 6)
  - Docker connectivity and database status monitoring

### Current Status
The project now has:
- Full container lifecycle management with image policy enforcement
- Asynchronous command execution with streaming output and security controls
- Complete filesystem operations with security controls
- MCP protocol integration with typed tool and resource endpoints
- Image allow-list validation and resolution with digest pinning
- Comprehensive security hardening (capability dropping, resource limits, audit logging)
- Warm container pool for fast provisioning (<1s attach time)
- Graceful shutdown with operation draining
- Boot recovery and automatic reconciliation
- Background maintenance and health monitoring
- **Complete audit logging for all operations with sensitive data redaction**
- **Prometheus metrics collection and exposure**
- **Admin tools for system status, container/exec listing, and manual operations**
- 201 unit and integration tests passing (100% success rate)
- Comprehensive error handling and resource management

## MCP Tools Reference

### Container Lifecycle Tools

#### `spawn`
Create and start a new container.

**Input:**
- `image` (string): Docker image reference
- `persistent` (boolean, default: false): Whether container persists across restarts
- `alias` (string, optional): User-friendly container alias
- `ttl_s` (integer, optional): Time to live for transient containers

**Output:**
- `container_id` (string): Opaque container ID (c_xxx format)
- `alias` (string, optional): Container alias if provided
- `status` (string): Container status

**Example:**
```json
{
  "image": "python:3.11-slim",
  "persistent": true,
  "alias": "dev-env"
}
```

#### `attach`
Attach a client to a container for session tracking.

**Input:**
- `target` (string): Container ID or alias
- `client_name` (string): Name of the attaching client
- `session_id` (string): Unique session identifier

**Output:**
- `container_id` (string): Actual container ID
- `alias` (string, optional): Container alias
- `roots` (array): Workspace roots (e.g., ["workspace:c_xxx"])

#### `kill`
Stop and remove a container.

**Input:**
- `container_id` (string): Container ID to remove
- `force` (boolean, default: false): Force removal without graceful stop

**Output:**
- `status` (string): Operation status

### Execution Tools

#### `exec_start`
Start command execution in a container.

**Input:**
- `container_id` (string): Target container ID
- `cmd` (array): Command and arguments
- `cwd` (string, default: "/workspace"): Working directory
- `env` (object, optional): Environment variables
- `as_root` (boolean, default: false): Execute as root user
- `timeout_s` (integer, default: 600): Execution timeout
- `idempotency_key` (string, optional): Key to prevent duplicate execution

**Output:**
- `exec_id` (string): Execution ID (e_xxx format)
- `status` (string): Initial status

**Example:**
```json
{
  "container_id": "c_123...",
  "cmd": ["python", "script.py"],
  "env": {"DEBUG": "1"},
  "timeout_s": 300
}
```

#### `exec_cancel`
Cancel a running execution.

**Input:**
- `exec_id` (string): Execution ID to cancel

**Output:**
- `status` (string): Cancellation status
- `exec_id` (string): Cancelled execution ID

#### `exec_poll`
Poll for execution output and completion status.

**Input:**
- `exec_id` (string): Execution ID
- `after_seq` (integer, default: 0): Return messages after this sequence number

**Output:**
- `messages` (array): Stream messages with sequence numbers
- `complete` (boolean): Whether execution is complete

### Filesystem Tools

#### `fs_read`
Read a file from the container workspace.

**Input:**
- `container_id` (string): Container ID
- `path` (string): File path within /workspace

**Output:**
- `content` (bytes): File content
- `etag` (string): Entity tag for concurrency control
- `size` (integer): File size in bytes
- `mime_type` (string, optional): MIME type

#### `fs_write`
Write a file to the container workspace.

**Input:**
- `container_id` (string): Container ID
- `path` (string): File path within /workspace
- `content` (bytes): File content
- `if_match_etag` (string, optional): Required ETag for conditional write

**Output:**
- `path` (string): Written file path
- `etag` (string): New entity tag
- `size` (integer): File size

#### `fs_delete`
Delete a file or directory.

**Input:**
- `container_id` (string): Container ID
- `path` (string): Path to delete

**Output:**
- `status` (string): Deletion status
- `path` (string): Deleted path

#### `fs_stat`
Get file or directory metadata.

**Input:**
- `container_id` (string): Container ID
- `path` (string): File/directory path

**Output:**
- `path` (string): File path
- `size` (integer): Size in bytes
- `is_dir` (boolean): Whether it's a directory
- `permissions` (string): File permissions
- `mtime` (datetime): Last modification time
- `etag` (string): Entity tag
- `mime_type` (string, optional): MIME type if file

#### `fs_list`
List directory contents.

**Input:**
- `container_id` (string): Container ID
- `path` (string, default: "/workspace"): Directory path

**Output:**
- `path` (string): Listed directory
- `entries` (array): File/directory entries with metadata

### Maintenance Tools

#### `reconcile`
Run container reconciliation to sync Docker state with database.

This tool performs:
- Discovery of containers with com.mcp.devbench label
- Adoption of running containers not in database
- Cleanup of stopped containers
- Removal of orphaned transient containers
- Cleanup of incomplete exec entries

**Input:** None

**Output:**
- `discovered` (integer): Containers found with MCP label
- `adopted` (integer): Containers added to database
- `cleaned_up` (integer): Missing containers marked stopped
- `orphaned` (integer): Old transients removed
- `errors` (integer): Errors encountered

**Example:**
```json
{
  "discovered": 5,
  "adopted": 1,
  "cleaned_up": 2,
  "orphaned": 1,
  "errors": 0
}
```

### Observability & Admin Tools

#### `metrics`
Get Prometheus metrics for monitoring.

Returns current metrics including:
- Container spawn counts by image
- Execution counts and durations
- Filesystem operation counts
- Active container and attachment gauges
- Memory usage by container

**Input:** None

**Output:**
- `metrics` (string): Prometheus-formatted metrics

**Example metrics output:**
```
# HELP mcp_devbench_container_spawns_total Total number of container spawns
# TYPE mcp_devbench_container_spawns_total counter
mcp_devbench_container_spawns_total{image="python:3.11"} 5.0
# HELP mcp_devbench_exec_total Total number of command executions
# TYPE mcp_devbench_exec_total counter
mcp_devbench_exec_total{container_id="c_123",status="success"} 10.0
# HELP mcp_devbench_active_containers Number of active containers
# TYPE mcp_devbench_active_containers gauge
mcp_devbench_active_containers 3.0
```

#### `system_status`
Get system health and status information.

**Input:** None

**Output:**
- `status` (string): Overall system status (healthy, degraded)
- `docker_connected` (boolean): Docker daemon connectivity
- `database_initialized` (boolean): Database initialization status
- `active_containers` (integer): Number of active containers
- `active_attachments` (integer): Number of active client attachments
- `version` (string): Server version

**Example:**
```json
{
  "status": "healthy",
  "docker_connected": true,
  "database_initialized": true,
  "active_containers": 3,
  "active_attachments": 2,
  "version": "0.1.0"
}
```

#### `garbage_collect`
Trigger manual garbage collection.

Cleans up:
- Orphaned transient containers
- Old completed exec records (>24h)
- Abandoned attachments

**Input:** None

**Output:**
- `containers_removed` (integer): Number of containers removed
- `execs_cleaned` (integer): Number of exec records cleaned
- `attachments_cleaned` (integer): Number of attachments cleaned

#### `list_containers`
List all containers with detailed information.

**Input:** None

**Output:**
- `containers` (array): List of container objects with id, docker_id, alias, image, status, persistent, created_at, last_seen

#### `list_execs`
List active command executions.

**Input:** None

**Output:**
- `execs` (array): List of execution objects with exec_id, container_id, cmd, as_root, started_at, status

See [mcp-devbench-work-breakdown.md](mcp-devbench-work-breakdown.md) for the complete implementation roadmap.

## License

See [LICENSE](LICENSE) for details.

## Contributing

This project is currently in active development. Contributions are welcome once the foundation layer is complete.
