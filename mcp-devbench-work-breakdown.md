> **Update — 2025-10-31**: This Work Breakdown has been updated for **Astral uv** and **FastMCP 2**. Any references to REST/FastAPI/SSE/WebSockets are superseded by **MCP-native tools/resources** with typed Pydantic models and **cursor-based poll** streaming. Use `pyproject.toml` + `uv.lock` (no `requirements.txt`).

# MCP DevBench - Work Breakdown for Coding Agents

## Implementation Strategy

**Approach:** Bottom-up implementation with vertical slices. Each feature should be independently testable with mock dependencies where needed.

**Tech Stack Assumptions:**
- Language: Python 3.11+ (async-first)
- Framework: FastMCP 2 (MCP-native server; no HTTP routes for tools) for HTTP/MCP poll-based streaming (bounded ring buffers + cursor)
- Docker SDK: docker-py
- State: SQLite with SQLAlchemy
- Testing: pytest with pytest-asyncio

---

## EPIC 1: Foundation Layer
_Goal: Core infrastructure and Docker integration_

### Feature 1.1: Project Scaffold & Configuration
**Dependencies:** None
**Deliverable:** Basic project structure with configuration management

```
Create a Python project structure for mcp-devbench with:
- FastMCP 2 (MCP-native server; no HTTP routes for tools) application skeleton
- ENV-based configuration system using Pydantic BaseSettings
- Docker client initialization with connection pooling
- Structured logging setup (JSON format)
- Health check endpoint
- Basic error handling middleware

Configuration variables to implement:
- MCP_ALLOWED_REGISTRIES (default: "docker.io,ghcr.io")
- MCP_STATE_DB (default: "./state.db")
- MCP_DRAIN_GRACE_S (default: 60)
- MCP_TRANSIENT_GC_DAYS (default: 7)

Include:
- `pyproject.toml` + `uv.lock` with all dependencies
- Dockerfile for the server itself
- docker-compose.yml for local development
- Basic README with setup instructions

Success Criteria:
- Server starts and responds to health check
- Configuration loads from environment
- Docker client connects successfully
```

### Feature 1.2: State Store & Schema
**Dependencies:** 1.1
**Deliverable:** SQLite database layer with SQLAlchemy models

```
Implement SQLite state management for mcp-devbench:

Database schema (SQLAlchemy models):
1. containers table:
   - id: String (PK) - format "c_{uuid}"
   - docker_id: String - actual Docker container ID
   - alias: String (nullable, unique) - user-friendly name
   - image: String - image reference used
   - digest: String (nullable) - resolved digest if pinned
   - persistent: Boolean - transient vs persistent
   - created_at: DateTime
   - last_seen: DateTime
   - ttl_s: Integer (nullable) - time to live
   - volume_name: String (nullable) - for persistent containers
   - status: String - "running", "stopped", "error"

2. attachments table:
   - id: Integer (PK)
   - container_id: String (FK)
   - client_name: String
   - session_id: String
   - attached_at: DateTime
   - detached_at: DateTime (nullable)

3. execs table:
   - exec_id: String (PK) - format "e_{uuid}"
   - container_id: String (FK)
   - cmd: JSON - command array
   - as_root: Boolean
   - started_at: DateTime
   - ended_at: DateTime (nullable)
   - exit_code: Integer (nullable)
   - usage: JSON (nullable) - {cpu_ms, mem_peak_mb, wall_ms}

Implement:
- Async database session management
- Migration system (Alembic)
- Repository pattern for each model
- Transaction support for atomic operations

Success Criteria:
- Database creates on startup
- All CRUD operations work
- Concurrent access handled safely
- Unit tests for all repository methods
```

### Feature 1.3: Docker Container Lifecycle Manager
**Dependencies:** 1.1, 1.2
**Deliverable:** Core container management without API endpoints

```
Create a ContainerManager class that handles Docker operations:

Core Methods:
- create_container(image: str, alias: Optional[str]) -> Container
  - Generate opaque ID (c_{uuid})
  - Apply labels: {"com.mcp.devbench": "true", "com.mcp.container_id": id}
  - Create with /workspace volume mount
  - Run as non-root user (UID 1000) by default
  - Network enabled
  - Save to state DB

- start_container(container_id: str) -> None
  - Start Docker container
  - Update state to "running"

- stop_container(container_id: str, timeout: int = 10) -> None
  - Stop Docker container gracefully
  - Update state

- remove_container(container_id: str, force: bool = False) -> None
  - Remove Docker container
  - Clean up volumes if transient
  - Remove from state DB

- get_container(identifier: str) -> Container
  - Lookup by ID or alias
  - Verify Docker container exists
  - Return container info

- list_containers(include_stopped: bool = False) -> List[Container]

Container Mount Configuration:
- Transient: Docker manages temporary volume
- Persistent: Named volume (mcpdevbench_{container_id})
- Mount point: always /workspace

Error Handling:
- ContainerNotFound
- ContainerAlreadyExists
- DockerAPIError

Success Criteria:
- Can create, start, stop, remove containers
- State stays synchronized with Docker
- Handles Docker daemon restarts gracefully
- Integration tests with real Docker
```

---

## EPIC 2: Command Execution Engine
_Goal: Async command execution with streaming output_

### Feature 2.1: Async Exec Core
**Dependencies:** 1.3
**Deliverable:** Basic command execution without streaming

```
Implement ExecManager class for running commands in containers:

Core Functionality:
- execute(container_id: str, cmd: List[str], 
         cwd: str = "/workspace",
         env: Dict[str, str] = None,
         as_root: bool = False,
         timeout_s: int = 600) -> str (exec_id)
  
  - Generate exec_id (e_{uuid})
  - Save to state DB immediately
  - Use docker-py exec_create/exec_start
  - Handle as_root via user parameter (0 if true, 1000 if false)
  - Capture stdout/stderr separately
  - Implement timeout with cleanup
  - Store exit code and resource usage

- get_exec_result(exec_id: str) -> ExecResult
  - Return status, exit_code, output (for now just concatenated)

Parallel Execution:
- Use asyncio.Semaphore(limit=4) per container
- Track active execs in memory
- Queue if at limit

Resource Tracking:
- Measure wall time
- Get container stats for CPU/memory if available
- Store in usage field

Success Criteria:
- Commands execute and return output
- Timeout works correctly
- as_root flag changes user context
- Parallel execution respects limits
- State persists across restarts
```

### Feature 2.2: Output Streaming with MCP poll-based streaming (bounded ring buffers + cursor)
**Dependencies:** 2.1
**Deliverable:** Real-time streaming of command output

```
Enhance ExecManager with streaming capabilities:

Streaming Infrastructure:
- Create OutputStreamer class
- Buffer management per exec (max 64MB default)
- Sequence numbering for ordered delivery
- Separate stdout/stderr streams

MCP poll-based streaming (bounded ring buffers + cursor) Implementation:
- /tool/exec returns exec_id immediately
- /stream/{exec_id} endpoint for MCP poll-based streaming (bounded ring buffers + cursor)
- Message format: {"seq": n, "stream": "stdout|stderr", "data": "...", "ts": "..."}
- Final message: {"exit_code": n, "usage": {...}}

Poll Fallback:
- /poll/{exec_id}?after_seq={n} for non-MCP poll-based streaming (bounded ring buffers + cursor) clients
- Returns buffered messages since sequence n
- Include "complete" flag when exec finishes

Backpressure:
- Per-client send buffers
- Slow client detection and disconnection
- Memory limits per exec

Success Criteria:
- Real-time output streaming works
- Messages arrive in order
- Both MCP poll-based streaming (bounded ring buffers + cursor) and poll modes function
- Memory limits enforced
- Multiple clients can stream same exec
```

### Feature 2.3: Exec Cancellation & Idempotency
**Dependencies:** 2.2
**Deliverable:** Cancel support and idempotent execution

```
Add cancellation and idempotency to ExecManager:

Cancellation:
- cancel(exec_id: str) -> None
  - Send SIGTERM to process
  - Wait 5 seconds
  - Send SIGKILL if still running
  - Mark as cancelled in DB
  - Stream cancellation event to clients

Idempotency:
- Accept idempotency_key in execute()
- Store key->exec_id mapping (24hr TTL)
- Return existing exec_id if key exists
- Prevent duplicate execution

Cleanup:
- Background task to clean old execs
- Configurable retention (default 24hr)
- Clean up orphaned Docker execs on startup

Success Criteria:
- Cancel terminates running commands
- Idempotency keys prevent duplicates
- Graceful handling of client disconnects
- State cleaned up properly
```

---

## EPIC 3: Filesystem Operations
_Goal: MCP ROOTS implementation for workspace access_

### Feature 3.1: Basic Filesystem Operations
**Dependencies:** 1.3
**Deliverable:** Single-file read/write/delete operations

```
Implement FilesystemManager for workspace operations:

Core Operations:
- read(container_id: str, path: str) -> bytes
  - Validate path under /workspace
  - Use docker cp or exec cat
  - Handle binary files
  - Return with metadata (size, mime_type)

- write(container_id: str, path: str, content: bytes, 
        if_match_etag: Optional[str] = None) -> str (new_etag)
  - Validate path under /workspace
  - Check etag if provided (return Conflict on mismatch)
  - Create parent directories if needed
  - Use docker cp or exec with heredoc
  - Calculate and return new etag

- delete(container_id: str, path: str) -> None
  - Validate path under /workspace
  - Use exec rm
  - Handle directories with rm -rf

- stat(container_id: str, path: str) -> FileInfo
  - Get size, permissions, mtime
  - Calculate etag
  - Determine file type

- list(container_id: str, path: str = "/workspace") -> List[FileInfo]
  - Use exec ls -la or find
  - Parse output
  - Include subdirectories

Path Security:
- Reject paths with .. components
- Ensure all paths start with /workspace
- Symlink validation

ETag Implementation:
- Use MD5 of content + mtime
- Store in extended attributes if possible
- Or maintain in SQLite cache

Success Criteria:
- All operations work with text and binary files
- Path validation prevents escapes
- ETags detect concurrent modifications
- Handles large files (>100MB)
```

### Feature 3.2: Batch Operations
**Dependencies:** 3.1
**Deliverable:** Atomic batch filesystem operations

```
Add batch operation support to FilesystemManager:

Batch API:
- batch(container_id: str, operations: List[Operation]) -> BatchResult
  - Operations: read, write, delete, move, copy
  - Execute in order
  - Rollback on any failure (best effort)
  - Return results for each operation

Transaction Support:
- Create temporary staging directory
- Perform operations in staging
- Atomic move to final locations
- Cleanup on failure

Optimizations:
- Combine multiple small writes into single docker cp
- Batch delete operations
- Parallel reads where safe

Conflict Resolution:
- Check all etags before starting
- Fail fast on conflicts
- Return detailed conflict information

Success Criteria:
- Batch operations appear atomic
- Rollback works on failure
- Performance better than individual operations
- Handles mixed read/write operations
```

### Feature 3.3: Import/Export Operations
**Dependencies:** 3.1
**Deliverable:** Tar-based bulk import/export

```
Implement bulk transfer operations:

Export:
- export_tar(container_id: str, path: str = "/workspace",
           include_globs: List[str] = ["**/*"],
           exclude_globs: List[str] = []) -> AsyncIterator[bytes]
  - Use docker exec tar with filters
  - Stream output in chunks
  - Support glob patterns
  - Compress with gzip by default

Import:
- import_tar(container_id: str, dest: str = "/workspace",
           stream: AsyncIterator[bytes]) -> ImportResult
  - Stream tar directly to docker exec tar -x
  - Validate destination path
  - Track bytes written
  - Preserve permissions/timestamps

Direct Download:
- download_file(container_id: str, path: str) -> FileResponse
  - Efficient single-file download
  - Support range requests
  - Set proper content-type

Safety:
- Validate tar contents don't escape workspace
- Size limits (configurable)
- Scan for suspicious patterns

Success Criteria:
- Can export/import full workspaces
- Streaming doesn't load all in memory
- Handles large archives (>1GB)
- Preserves file attributes
```

---

## EPIC 4: MCP Protocol Integration
_Goal: Expose as MCP server with proper tool/resource definitions_

### Feature 4.1: MCP Tool Endpoints
**Dependencies:** 1.3, 2.1, 3.1
**Deliverable:** HTTP endpoints matching MCP tool specifications

```
Implement FastMCP 2 (MCP-native server; no HTTP routes for tools) routes for MCP tools:

Tool Endpoints:
- POST /tool/spawn
  Input: {image, persistent, alias}
  Create container (warm default logic)
  Return: {container_id, alias}

- POST /tool/attach
  Input: {target, client_name, session_id}
  Record attachment in DB
  Return: {container_id, alias, roots: ["workspace:c_xxx"]}

- POST /tool/kill
  Input: {container_id}
  Stop and remove container
  Clean up attachments
  Return: {status: "stopped"}

- POST /tool/exec
  Input: {container_id, cmd, cwd, env, as_root, timeout_s, idempotency_key}
  Start execution async
  Return: {exec_id}

- POST /tool/cancel
  Input: {exec_id}
  Cancel running exec
  Return: {status: "cancelled"}

Request Validation:
- Pydantic models for all inputs/outputs
- Clear error messages
- Request ID tracking

Error Responses:
- Standard error format: {code, message, details}
- Proper HTTP status codes
- Request correlation IDs

Success Criteria:
- All endpoints follow spec exactly
- Validation catches malformed requests
- Errors follow taxonomy from spec
- FastMCP auto-derived schemas from Pydantic models schema generates correctly
```

### Feature 4.2: MCP Resource Implementation
**Dependencies:** 3.1
**Deliverable:** ROOTS resource for workspace access

```
Implement MCP resource endpoints:

Resource Definition:
- workspace:{container_id} resource type
- Capabilities: read, write, list, stat, delete

Resource Endpoints:
- GET /resource/workspace/{container_id}/read?path=...
- POST /resource/workspace/{container_id}/write
- DELETE /resource/workspace/{container_id}/delete?path=...
- GET /resource/workspace/{container_id}/stat?path=...
- GET /resource/workspace/{container_id}/list?path=...

Access Control:
- Validate container_id exists
- Check client has active attachment
- Enforce /workspace scope

Metadata:
- Return proper content-types
- Include etags in responses
- Support if-match headers

Success Criteria:
- Resources accessible per MCP spec
- Proper access control
- ETags work for concurrency
- Handles binary content correctly
```

### Feature 4.3: Streaming & MCP poll-based streaming (bounded ring buffers + cursor) Transport
**Dependencies:** 2.2
**Deliverable:** Proper MCP poll-based streaming (bounded ring buffers + cursor) implementation for MCP

```
Implement streaming transport for MCP:

MCP poll-based streaming (bounded ring buffers + cursor) Endpoints:
- GET /stream/{exec_id}
  MCP poll-based streaming (bounded ring buffers + cursor) stream
  Heartbeat every 30s
  Auto-close on completion

Poll Endpoints:
- GET /poll/{exec_id}?after_seq=...
  Return messages since sequence
  Include completion status

Export Streaming:
- POST /tool/export_tar
  Stream tar data
  Chunked transfer encoding

Import Streaming:
- POST /tool/import_tar
  Accept streaming body
  Progress updates via separate endpoint

Connection Management:
- Track active streams per client
- Limit concurrent streams
- Clean up on disconnect

Success Criteria:
- MCP poll-based streaming (bounded ring buffers + cursor) works with various clients
- Poll fallback functions correctly
- Large transfers don't timeout
- Graceful handling of disconnects
```

---

## EPIC 5: Image & Security Management
_Goal: Implement image policies and security controls_

### Feature 5.1: Image Allow-List & Resolution
**Dependencies:** 1.1, 1.3
**Deliverable:** Image validation and resolution system

```
Implement ImagePolicyManager:

Configuration:
- Parse MCP_ALLOWED_REGISTRIES
- Parse MCP_ALLOWED_IMAGES (aliases and refs)
- Support tag and digest formats

Resolution Logic:
- resolve_image(requested: str) -> ResolvedImage
  Check against allow-lists
  Resolve aliases to refs
  Optional pin to digest
  Pull if not present

Registry Authentication:
- Load docker config from MCP_DOCKER_CONFIG_JSON
- Support multiple registries
- Handle private registries

Validation:
- Reject disallowed registries
- Reject unlisted images
- Validate image manifests

Caching:
- Cache resolved digests
- Periodic refresh for tags
- Handle registry rate limits

Success Criteria:
- Only allowed images can be used
- Aliases resolve correctly
- Private registries work with auth
- Clear errors for policy violations
```

### Feature 5.2: Security Controls
**Dependencies:** 1.3, 2.1
**Deliverable:** Runtime security implementation

```
Implement security controls:

Container Security:
- Drop capabilities: CAP_SYS_ADMIN, CAP_NET_ADMIN, etc.
- No privileged mode ever
- Read-only root filesystem (except /workspace)
- No host network mode
- No Docker socket mounting

User Management:
- Default UID 1000 (non-root)
- as_root policy enforcement
- Per-image root allow-list
- No sudo in containers

Network Controls:
- Egress allowed by default
- DNS configuration
- Optional network policies (future)

Resource Limits:
- Memory limits per container
- CPU quotas
- Disk quotas for workspace
- PID limits

Audit:
- Log all security-relevant operations
- Include client identity
- Track privilege escalations

Success Criteria:
- Containers run with minimal privileges
- Root access properly controlled
- Resource limits enforced
- Audit trail complete
```

### Feature 5.3: Warm Container Pool
**Dependencies:** 1.3, 5.1
**Deliverable:** Pre-warmed container management

```
Implement warm container pool:

Pool Management:
- Maintain one warm default container
- Create on startup if missing
- Health check every 60s
- Recreate if unhealthy

Fast Attach:
- spawn() can claim warm container
- Atomic claim operation
- Start new warm container async
- Fall back to cold start if none available

Configuration:
- MCP_DEFAULT_IMAGE_ALIAS
- MCP_WARM_POOL_ENABLED (default true)
- MCP_WARM_HEALTH_CHECK_INTERVAL

Lifecycle:
- Warm containers marked specially in DB
- Clean workspace between uses
- Reset environment
- Preserve base image state

Success Criteria:
- First attach is fast (<1s)
- Health checks detect issues
- Seamless failover on unhealthy
- No resource waste when idle
```

---

## EPIC 6: State Management & Recovery
_Goal: Durability and crash recovery_

### Feature 6.1: Graceful Shutdown
**Dependencies:** All previous
**Deliverable:** Clean shutdown handling

```
Implement shutdown coordinator:

Shutdown Sequence:
- Catch SIGTERM/SIGINT
- Stop accepting new requests
- Cancel new spawns/execs
- Drain active operations (MCP_DRAIN_GRACE_S)
- Stop transient containers
- Preserve persistent containers
- Flush state to disk
- Exit cleanly

Drain Logic:
- Wait for active execs up to timeout
- Force-cancel after grace period
- Stream shutdown notices to clients
- Save partial results

State Preservation:
- Mark transient containers for cleanup
- Save exec results
- Update last_seen timestamps
- Commit all transactions

Connection Handling:
- Close MCP poll-based streaming (bounded ring buffers + cursor) streams gracefully
- Send shutdown notification
- Clean up client sessions

Success Criteria:
- No data loss on shutdown
- Clients notified properly
- Transient containers stopped
- Persistent containers survive
```

### Feature 6.2: Boot Recovery & Reconciliation
**Dependencies:** 1.2, 1.3
**Deliverable:** Startup reconciliation with Docker state

```
Implement boot recovery system:

Discovery:
- Find containers with com.mcp.devbench=true label
- Match against state DB
- Identify orphans and zombies

Reconciliation:
- Adopt running containers into state
- Clean up stopped containers not in DB
- Restore aliases from DB
- Recreate warm default if missing

Orphan Handling:
- Identify containers without recent activity
- Check against MCP_TRANSIENT_GC_DAYS
- Clean up expired transients
- Preserve persistent regardless of age

State Repair:
- Fix inconsistent states
- Clean up incomplete execs
- Restore client attachments where valid
- Reset locks and semaphores

Startup Sequence:
1. Load configuration
2. Connect to Docker
3. Initialize database
4. Run reconciliation
5. Start warm pool
6. Begin accepting requests

Success Criteria:
- Survives Docker daemon restart
- Survives server crash
- No container leaks
- State consistency restored
```

### Feature 6.3: Background Maintenance
**Dependencies:** 6.2
**Deliverable:** Periodic cleanup and maintenance tasks

```
Implement background maintenance:

Garbage Collection:
- Run every hour
- Clean orphaned transients (MCP_TRANSIENT_GC_DAYS)
- Remove completed execs older than 24h
- Vacuum SQLite database
- Clean up abandoned attachments

Health Monitoring:
- Check container health
- Verify Docker connectivity
- Monitor disk space
- Alert on resource exhaustion

State Sync:
- Periodic Docker state verification
- Fix drift between DB and Docker
- Update last_seen timestamps
- Refresh container stats

Metrics Collection:
- Count active containers
- Track resource usage
- Monitor exec performance
- Export to metrics backend

Log Rotation:
- Rotate audit logs
- Compress old logs
- Clean up based on retention

Success Criteria:
- No resource leaks over time
- Automatic recovery from drift
- Metrics exported correctly
- Logs properly maintained
```

---

## EPIC 7: Observability & Operations
_Goal: Production-ready monitoring and debugging_

### Feature 7.1: Structured Audit Logging
**Dependencies:** All endpoints
**Deliverable:** Complete audit trail

```
Implement audit logging system:

Log Events:
- Container: spawn, attach, kill, state_change
- Exec: start, output, cancel, complete
- Filesystem: read, write, delete, batch
- Security: as_root, policy_violation
- Transfer: export, import

Log Format (JSON):
{
  "timestamp": "ISO8601",
  "event_type": "exec_start",
  "container_id": "c_xxx",
  "client_name": "dev-ui",
  "session_id": "uuid",
  "details": {...},
  "correlation_id": "request_id"
}

Storage:
- Write to stdout by default
- Support file output
- Buffer for performance
- Async write to not block operations

Privacy:
- Redact sensitive environment variables
- Hash client IPs
- Configurable detail level

Success Criteria:
- Every operation logged
- Logs are structured and parseable
- No performance impact
- Can reconstruct session from logs
```

### Feature 7.2: Metrics & Monitoring
**Dependencies:** All components
**Deliverable:** Prometheus metrics endpoint

```
Implement metrics collection:

Metrics to Track:
- Counter: container_spawns_total{image}
- Counter: exec_total{container_id, status}
- Counter: fs_operations_total{op_type}
- Histogram: exec_duration_seconds
- Histogram: output_bytes
- Gauge: active_containers
- Gauge: active_attachments
- Gauge: memory_usage_bytes{container_id}

Implementation:
- Use prometheus-client library
- Expose at /metrics
- Update metrics async
- Include custom business metrics

Alerts (examples):
- High failure rate
- Memory exhaustion
- Slow executions
- Orphaned containers

Performance:
- Minimal overhead
- Batch updates
- Async collection

Success Criteria:
- All key metrics exposed
- Prometheus can scrape
- Grafana dashboards work
- No performance degradation
```

### Feature 7.3: Debug & Admin Tools
**Dependencies:** All components
**Deliverable:** Administrative endpoints and debugging tools

```
Implement admin interface:

Admin Endpoints:
- GET /admin/status - System health
- GET /admin/containers - Detailed container list
- GET /admin/execs - Active executions
- POST /admin/reconcile - Force reconciliation
- POST /admin/gc - Trigger garbage collection

Debug Features:
- Verbose logging mode toggle
- Trace specific container/exec
- Dump state for debugging
- Simulate failures for testing

Dry-run Mode:
- Test configuration changes
- Preview what would be deleted
- Validate policies
- Check image resolution

CLI Tool:
- mcp-devbench-admin script
- Container management commands
- State inspection
- Manual reconciliation

Success Criteria:
- Admin can diagnose issues
- Debug mode helps development
- CLI tool works for operations
- No security exposure in production
```

---

## Testing Strategy

### Unit Tests (Per Feature)
- Mock Docker API
- Mock database
- Test business logic
- Test error handling

### Integration Tests (Per Epic)
- Real Docker daemon
- Real SQLite
- Test full workflows
- Test failure scenarios

### End-to-End Tests (System)
- Multi-client scenarios
- Crash recovery
- Performance benchmarks
- Security validation

### Performance Targets
- Container spawn: <2s cold, <500ms warm
- Exec start: <100ms
- Filesystem ops: <50ms for small files
- MCP poll-based streaming (bounded ring buffers + cursor) latency: <10ms
- Concurrent clients: 100+
- Parallel execs: 4+ per container

---

## Implementation Order

### Phase 1: MVP (Weeks 1-2)
1. Feature 1.1: Project Scaffold
2. Feature 1.2: State Store
3. Feature 1.3: Container Lifecycle
4. Feature 2.1: Async Exec Core
5. Feature 4.1: MCP Tool Endpoints (spawn, attach, kill, exec)

### Phase 2: Core Features (Weeks 3-4)
1. Feature 2.2: Output Streaming
2. Feature 3.1: Basic Filesystem Ops
3. Feature 4.2: MCP Resources
4. Feature 5.1: Image Allow-lists
5. Feature 6.2: Boot Recovery

### Phase 3: Production Ready (Weeks 5-6)
1. Feature 2.3: Cancellation & Idempotency
2. Feature 3.3: Import/Export
3. Feature 5.2: Security Controls
4. Feature 6.1: Graceful Shutdown
5. Feature 7.1: Audit Logging

### Phase 4: Polish (Week 7)
1. Feature 3.2: Batch Operations
2. Feature 5.3: Warm Container Pool
3. Feature 6.3: Background Maintenance
4. Feature 7.2: Metrics
5. Feature 7.3: Admin Tools

---

## Delivery Instructions for Coding Agents

Each feature above should be delivered to a coding agent as:

1. **Context**: The feature description box
2. **Dependencies**: List of completed features needed
3. **Test Requirements**: Unit and integration tests
4. **Success Criteria**: From the feature description

Example prompt format:
```
Implement [Feature Name] for the MCP DevBench project.

Context:
[Copy the feature description box]

You have access to:
- [List completed dependencies]

Deliver:
- Source code implementation
- Unit tests with mocked dependencies
- Integration test if applicable
- Documentation updates

Follow Python best practices, use type hints, and ensure async-safe operations.
```

---

## Coding Agent Tips

1. **Feature Independence**: Each feature should work with mocked dependencies
2. **Error Handling**: Use the error taxonomy from the spec
3. **Async-First**: All I/O operations should be async
4. **Type Safety**: Use Pydantic models for all API contracts
5. **Testing**: Aim for >80% coverage with both unit and integration tests
6. **Documentation**: Include docstrings and update README with each feature
7. **Performance**: Profile critical paths, especially streaming operations
8. **Security**: Never trust client input, validate everything

---

## Updated Epics (delta for uv + FastMCP 2)

**Intent:** Keep the original epics intact; the following deltas replace HTTP-centric work with **MCP-native** equivalents and add **uv** packaging.

### Epic 0 — Project Bootstrap (uv)
- Replace requirements files with `pyproject.toml`; commit `uv.lock`.
- CI uses `uv sync` and `uv run pytest -q` with cache.
- Entrypoint: `python -m mcp_devbench.server`.

### Epic 1 — State & Repositories (no change in spirit)
- SQLite (WAL) + SQLAlchemy + Alembic; same entities (containers, execs, attachments).
- Gate server start until migrations are applied.

### Epic 2 — Managers (Docker/Exec/FS/Attachments)
- Logic unchanged; continue to encapsulate Docker SDK and filesystem policy.
- Add ring-buffer facilities for exec output with capped memory.

### Epic 3 — **MCP Server & Tools (replaces HTTP/API)**
- Implement **FastMCP 2** server in `src/mcp_devbench/server.py`.
- Tools:
  - lifecycle: `spawn`, `kill`, `attach`
  - exec: `exec_start`, `exec_poll`, `exec_cancel`
  - fs: `fs_read`, `fs_write`, `fs_tar_read`, `fs_tar_write`
  - attachments: `attach_put`, `attach_get`
  - ops: `reconcile`, `metrics_dump` (optional)
  - support: `health`, `policy_check`
- Typed **Pydantic v2** models define tool schemas automatically.
- Optional **MCP resources** for workspace access: `workspace:{container_id}`.

### Epic 4 — Policy & Security
- Central policy module: registry allow-list, argv/path/tar validation, attachment quotas.
- Containers run non-root; drop capabilities; set CPU/mem/pids limits.

### Epic 5 — Streaming & Backpressure
- Cursor-based polling over MCP; bounded stdout/stderr ring buffers.
- Deterministic `{truncated, done, exit_code}` semantics; monotonic cursors.

### Epic 6 — Reconciliation
- Sweep on boot and on-demand: zombie containers, orphan exec buffers, stale volumes.
- Optional warm-pool with CAS claim tokens and TTLs.

### Epic 7 — Observability
- Prometheus counters for tool calls, errors by code, bytes in/out, truncations, reconcile actions.
- Structured JSON logs with operation ids; avoid secrets.
- `health()` is the canonical liveness/readiness probe.

### Epic 8 — Packaging & Deployment (uv + Docker)
- Multi-stage Dockerfile using **uv** for fast wheel builds.
- Minimal final image, non-root user; optional `/metrics` exporter as a sidecar.
- Compose example using sibling Docker (`/var/run/docker.sock`) or rootless host Docker.

## Acceptance Tests (System)
- Full flow (spawn → exec_start/poll → fs_write/read → tar → attachments) under load without OOM.
- Policy denials return stable `code` values (`POLICY_DENIED`, etc.).
- Reconcile deterministically removes zombies and reclaims resources.
- Health remains green through transient Docker hiccups.

## Runbook (uv)
- Install: `uv sync`
- Develop: `uv run python -m mcp_devbench.server`
- Test: `uv run pytest -q`
- Build image: multi-stage Dockerfile; CMD `python -m mcp_devbench.server`
