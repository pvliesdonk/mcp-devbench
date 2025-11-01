# MCP DevBench Implementation Roadmap

**Version:** 1.0
**Last Updated:** 2025-11-01
**Current Version:** 0.1.0

---

## Executive Summary

This roadmap consolidates recommendations from comprehensive code analysis and defines a prioritized path for evolving MCP DevBench from a solid v0.1 release to an enterprise-grade container management platform.

### Key Objectives

1. **Harden Production Readiness** - Comprehensive testing, security scanning, and operational tooling
2. **Improve Performance** - Async I/O optimization, caching, and resource management
3. **Enable Scale** - Multi-instance deployment, PostgreSQL support, distributed locking
4. **Enhance Developer Experience** - Better documentation, tooling, and debugging capabilities
5. **Enterprise Features** - Multi-tenancy, advanced security policies, and observability

### Success Metrics

- **Test Coverage:** >85% (currently ~72%)
- **Performance:** <100ms p95 latency for API calls
- **Scalability:** Support 100+ concurrent containers
- **Security:** Zero high/critical vulnerabilities
- **Documentation:** Complete API docs, runbooks, and contributor guides

---

## Quick Wins (Priority 0: Immediate)

**Timeline:** 1-2 weeks | **Effort:** Low | **Impact:** High

These improvements can be implemented immediately with minimal architectural changes but provide significant value.

### QW-1: Isolate Blocking I/O

**Problem:** Synchronous file operations and Docker API calls block the asyncio event loop, degrading performance under load.

**Solution:**
```python
# Feature 1.1: Wrap filesystem operations in asyncio.to_thread
# Location: src/mcp_devbench/managers/filesystem_manager.py

async def read(self, container_id: str, path: str) -> tuple[bytes, FileInfo]:
    """Read file with non-blocking I/O."""
    def _blocking_read():
        # Existing synchronous code
        ...

    return await asyncio.to_thread(_blocking_read)

# Feature 1.2: Wrap Docker API calls in thread pool
# Location: src/mcp_devbench/utils/docker_client.py

async def async_docker_call(func, *args, **kwargs):
    """Execute blocking Docker SDK calls in thread pool."""
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=10)
    return await loop.run_in_executor(executor, func, *args, **kwargs)
```

**Files to Modify:**
- `src/mcp_devbench/managers/filesystem_manager.py`
- `src/mcp_devbench/managers/container_manager.py`
- `src/mcp_devbench/utils/docker_client.py`

**Tests Required:**
- `tests/unit/test_async_filesystem.py`
- `tests/performance/test_concurrent_operations.py`

**Success Criteria:**
- All blocking I/O wrapped in `asyncio.to_thread` or thread pool
- Performance benchmarks show >50% improvement in concurrent load
- Zero blocking calls detected by async linter

---

### QW-2: Add Pre-commit Hooks

**Problem:** No automated quality checks before commits.

**Solution:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

**Files to Create:**
- `.pre-commit-config.yaml`

**Documentation:**
- Update `CONTRIBUTING.md` with pre-commit setup instructions

**Success Criteria:**
- Pre-commit hooks run on every commit
- CI validates hooks are passing

---

### QW-3: Add Type Checking with mypy

**Problem:** Missing static type checking leads to runtime type errors.

**Solution:**
```toml
# pyproject.toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
disallow_untyped_defs = true
disallow_any_generics = true
check_untyped_defs = true
no_implicit_optional = true
strict_equality = true

[[tool.mypy.overrides]]
module = "docker.*"
ignore_missing_imports = true
```

**Files to Modify:**
- `pyproject.toml`
- `.github/workflows/ci.yml` (add mypy step)
- Add type hints to all functions lacking them

**Success Criteria:**
- 100% type coverage in core modules
- mypy passes in CI with strict mode

---

### QW-4: Security Scanning Integration

**Problem:** No automated vulnerability scanning for dependencies or containers.

**Solution:**
```yaml
# .github/workflows/security.yml
name: Security Scanning

on:
  push:
    branches: [main]
  pull_request:
  schedule:
    - cron: '0 0 * * 0'

jobs:
  dependency-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Run Safety check
        run: |
          uv pip install safety
          uv run safety check --json

      - name: Run Trivy filesystem scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          scan-ref: '.'
          severity: 'HIGH,CRITICAL'
          format: 'sarif'
          output: 'trivy-results.sarif'

      - name: Upload to GitHub Security
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-results.sarif'

  container-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build container
        run: docker build -t mcp-devbench:test .

      - name: Run Trivy container scan
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: 'mcp-devbench:test'
          format: 'sarif'
          output: 'trivy-container.sarif'

      - name: Upload results
        uses: github/codeql-action/upload-sarif@v3
        with:
          sarif_file: 'trivy-container.sarif'
```

**Files to Create:**
- `.github/workflows/security.yml`

**Success Criteria:**
- Security scanning runs on every PR and weekly
- Zero high/critical vulnerabilities
- SARIF results uploaded to GitHub Security tab

---

### QW-5: Add Idempotency to spawn Tool

**Problem:** Duplicate containers created on retry due to network timeouts.

**Solution:**
```python
# Feature 5.1: Add idempotency_key to SpawnInput
# Location: src/mcp_devbench/mcp_tools.py

class SpawnInput(BaseModel):
    image: str
    persistent: bool = False
    alias: str | None = None
    ttl_s: int | None = None
    idempotency_key: str | None = None  # NEW

# Feature 5.2: Track idempotency keys in database
# Location: src/mcp_devbench/models/containers.py

class Container(Base):
    # ... existing fields ...
    idempotency_key: Mapped[str | None] = mapped_column(String, index=True, unique=True)
    idempotency_key_created_at: Mapped[datetime | None] = mapped_column(DateTime)

# Feature 5.3: Implement idempotent spawn logic
# Location: src/mcp_devbench/managers/container_manager.py

async def create_container(
    self,
    image: str,
    alias: str | None = None,
    persistent: bool = False,
    ttl_s: int | None = None,
    idempotency_key: str | None = None,
) -> Container:
    """Create container with idempotency support."""

    # Check for existing container with same idempotency key
    if idempotency_key:
        async with self.db_manager.get_session() as session:
            repo = ContainerRepository(session)
            existing = await repo.get_by_idempotency_key(idempotency_key)

            if existing:
                # Check if key is still valid (within 24 hours)
                if existing.idempotency_key_created_at:
                    age = datetime.now(timezone.utc) - existing.idempotency_key_created_at
                    if age.total_seconds() < 86400:  # 24 hours
                        logger.info(f"Returning existing container for idempotency key: {idempotency_key}")
                        return existing

    # Proceed with normal creation...
```

**Files to Modify:**
- `src/mcp_devbench/mcp_tools.py`
- `src/mcp_devbench/models/containers.py`
- `src/mcp_devbench/managers/container_manager.py`
- `src/mcp_devbench/repositories/containers.py`
- Database migration: `alembic/versions/add_idempotency_key.py`

**Tests Required:**
- `tests/unit/test_spawn_idempotency.py`

**Success Criteria:**
- Duplicate spawn requests with same idempotency_key return existing container
- Idempotency keys expire after 24 hours
- Background maintenance cleans expired keys

---

### QW-6: Fine-Grained Docker Exception Handling

**Problem:** Generic exception handling makes debugging difficult.

**Solution:**
```python
# Feature 6.1: Create specific exception types
# Location: src/mcp_devbench/utils/exceptions.py

class ImageNotFoundError(DockerAPIError):
    """Docker image not found."""
    pass

class ContainerExitedError(DockerAPIError):
    """Container exited unexpectedly."""
    pass

class DockerDaemonUnreachableError(DockerAPIError):
    """Docker daemon is unreachable."""
    pass

# Feature 6.2: Refine exception handling in Docker client
# Location: src/mcp_devbench/utils/docker_client.py

def handle_docker_error(func):
    """Decorator to convert Docker exceptions to application exceptions."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except docker.errors.ImageNotFound as e:
            raise ImageNotFoundError(f"Image not found: {e}")
        except docker.errors.NotFound as e:
            raise ContainerNotFoundError(f"Container not found: {e}")
        except docker.errors.APIError as e:
            if "daemon" in str(e).lower():
                raise DockerDaemonUnreachableError(f"Docker daemon unreachable: {e}")
            raise DockerAPIError(f"Docker API error: {e}")
    return wrapper
```

**Files to Modify:**
- `src/mcp_devbench/utils/exceptions.py`
- `src/mcp_devbench/utils/docker_client.py`
- `src/mcp_devbench/managers/container_manager.py`
- `src/mcp_devbench/managers/image_policy_manager.py`

**Success Criteria:**
- All Docker errors mapped to specific exceptions
- Error messages provide actionable information
- Tests verify exception handling

---

### QW-7: Add .dockerignore

**Problem:** Unnecessary files included in Docker build context.

**Solution:**
```
# .dockerignore
.git
.github
.venv
.pytest_cache
.ruff_cache
.mypy_cache
__pycache__
*.pyc
*.pyo
*.pyd
.Python
*.egg-info
dist/
build/
htmlcov/
.coverage
coverage.xml
*.log
.env
.env.*
tests/
docs/
*.md
!README.md
Dockerfile
docker-compose.yml
.dockerignore
.gitignore
```

**Files to Create:**
- `.dockerignore`

**Success Criteria:**
- Docker build context reduced by >50%
- Build time improved

---

## Epic 1: Testing & Quality Assurance

**Priority:** P0 (Critical)
**Timeline:** 3-4 weeks
**Effort:** Medium-High
**Owner:** QA/Testing Team

### Overview

Establish comprehensive test coverage and quality assurance practices to ensure reliability and prevent regressions.

### Features

#### E1-F1: End-to-End Test Framework

**Description:** Create E2E tests simulating complete MCP client workflows.

**Implementation:**
```python
# tests/e2e/test_complete_workflow.py

import pytest
from mcp_devbench.server import mcp
from mcp_devbench.mcp_tools import *

@pytest.mark.e2e
async def test_complete_container_lifecycle():
    """Test full workflow: spawn -> attach -> exec -> fs -> kill."""

    # 1. Spawn container
    spawn_result = await spawn(SpawnInput(
        image="python:3.11-slim",
        persistent=False,
        alias="e2e-test-container"
    ))
    container_id = spawn_result.container_id

    try:
        # 2. Attach to container
        attach_result = await attach(AttachInput(
            target=container_id,
            client_name="e2e-client",
            session_id="e2e-session"
        ))
        assert attach_result.container_id == container_id

        # 3. Execute command
        exec_result = await exec_start(ExecInput(
            container_id=container_id,
            cmd=["echo", "hello world"],
            timeout_s=30
        ))

        # 4. Poll for output
        poll_result = await exec_poll(ExecPollInput(
            exec_id=exec_result.exec_id,
            after_seq=0
        ))
        assert poll_result.complete
        assert any("hello world" in msg.data for msg in poll_result.messages if msg.data)

        # 5. Write file
        write_result = await fs_write(FileWriteInput(
            container_id=container_id,
            path="/workspace/test.txt",
            content=b"test content"
        ))
        assert write_result.size == len(b"test content")

        # 6. Read file back
        read_result = await fs_read(FileReadInput(
            container_id=container_id,
            path="/workspace/test.txt"
        ))
        assert read_result.content == b"test content"

        # 7. List files
        list_result = await fs_list(FileListInput(
            container_id=container_id,
            path="/workspace"
        ))
        assert any(entry.path == "/workspace/test.txt" for entry in list_result.entries)

        # 8. Delete file
        delete_result = await fs_delete(FileDeleteInput(
            container_id=container_id,
            path="/workspace/test.txt"
        ))
        assert delete_result.status == "deleted"

    finally:
        # 9. Kill container
        kill_result = await kill(KillInput(
            container_id=container_id,
            force=True
        ))
        assert kill_result.status == "stopped"

@pytest.mark.e2e
async def test_concurrent_executions():
    """Test multiple concurrent executions in same container."""
    # Spawn container
    spawn_result = await spawn(SpawnInput(image="python:3.11-slim"))
    container_id = spawn_result.container_id

    try:
        # Start 4 concurrent executions (max limit)
        exec_tasks = []
        for i in range(4):
            exec_result = await exec_start(ExecInput(
                container_id=container_id,
                cmd=["sleep", "5"],
                timeout_s=10
            ))
            exec_tasks.append(exec_result.exec_id)

        assert len(exec_tasks) == 4

        # Try to exceed limit (should queue or fail gracefully)
        with pytest.raises(ConcurrencyLimitExceededError):
            await exec_start(ExecInput(
                container_id=container_id,
                cmd=["sleep", "1"],
                timeout_s=5
            ))
    finally:
        await kill(KillInput(container_id=container_id, force=True))

@pytest.mark.e2e
async def test_persistent_container_survives_restart():
    """Test persistent containers survive server restart."""
    # This test would require special setup to restart the server
    pass

@pytest.mark.e2e
async def test_warm_pool_fast_attach():
    """Test warm pool provides sub-second attach time."""
    import time

    start_time = time.time()
    attach_result = await attach(AttachInput(
        target="warm-pool",  # Special target for warm pool
        client_name="perf-test",
        session_id="perf-session"
    ))
    attach_duration = time.time() - start_time

    assert attach_duration < 1.0  # Sub-second attach

    # Clean up
    await kill(KillInput(container_id=attach_result.container_id, force=True))
```

**Files to Create:**
- `tests/e2e/test_complete_workflow.py`
- `tests/e2e/test_error_scenarios.py`
- `tests/e2e/test_security.py`
- `tests/e2e/test_observability.py`

**Configuration:**
```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "e2e: End-to-end tests (deselect with '-m \"not e2e\"')",
    "integration: Integration tests",
    "performance: Performance benchmarks",
]
```

**Success Criteria:**
- 20+ E2E tests covering all major workflows
- E2E tests run in CI on every PR
- 100% of critical user journeys covered

---

#### E1-F2: Property-Based Testing

**Description:** Add hypothesis-based property testing for invariants.

**Implementation:**
```python
# tests/property/test_path_security.py

from hypothesis import given, strategies as st
from mcp_devbench.managers.filesystem_manager import FilesystemManager
from mcp_devbench.utils.exceptions import PathSecurityError

@given(st.text())
def test_path_validation_never_escapes_workspace(path: str):
    """Property: validate_path should never allow escape from /workspace."""
    manager = FilesystemManager()

    try:
        validated = manager._validate_path(path)
        # If validation passes, path must start with /workspace
        assert validated.startswith('/workspace'), \
            f"Path {validated} does not start with /workspace"
    except PathSecurityError:
        # Expected for malicious paths
        pass

@given(st.integers(min_value=0, max_value=1000000), st.integers(min_value=0, max_value=1000000))
def test_etag_collisions_are_rare(size1: int, size2: int):
    """Property: ETags should rarely collide for different file sizes."""
    from mcp_devbench.managers.filesystem_manager import _compute_etag
    import time

    etag1 = _compute_etag(b"x" * size1, time.time())
    etag2 = _compute_etag(b"y" * size2, time.time() + 0.001)

    if size1 != size2:
        assert etag1 != etag2

# tests/property/test_idempotency.py

@given(st.text(min_size=1, max_size=100))
async def test_spawn_idempotency_is_reliable(idempotency_key: str):
    """Property: Multiple spawns with same key should return same container."""
    results = []

    for _ in range(3):
        result = await spawn(SpawnInput(
            image="python:3.11-slim",
            idempotency_key=idempotency_key
        ))
        results.append(result.container_id)

    # All results should be the same container
    assert len(set(results)) == 1

    # Clean up
    await kill(KillInput(container_id=results[0], force=True))
```

**Files to Create:**
- `tests/property/test_path_security.py`
- `tests/property/test_idempotency.py`
- `tests/property/test_concurrency.py`

**Dependencies:**
```toml
# pyproject.toml
[project.optional-dependencies]
dev = [
    # ... existing ...
    "hypothesis>=6.0.0",
]
```

**Success Criteria:**
- 10+ property-based tests
- Tests discover edge cases not covered by unit tests

---

#### E1-F3: Performance Benchmarking

**Description:** Establish performance baselines and regression testing.

**Implementation:**
```python
# tests/performance/test_benchmarks.py

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

@pytest.mark.benchmark
def test_spawn_container_performance(benchmark):
    """Benchmark container spawn time."""

    async def spawn_container():
        result = await spawn(SpawnInput(image="alpine:latest"))
        await kill(KillInput(container_id=result.container_id, force=True))

    benchmark(asyncio.run, spawn_container())

@pytest.mark.benchmark
def test_exec_throughput(benchmark):
    """Benchmark command execution throughput."""

    async def run_exec():
        # Setup
        spawn_result = await spawn(SpawnInput(image="python:3.11-slim"))
        container_id = spawn_result.container_id

        try:
            # Benchmark
            exec_result = await exec_start(ExecInput(
                container_id=container_id,
                cmd=["echo", "test"],
                timeout_s=5
            ))

            # Wait for completion
            while True:
                poll_result = await exec_poll(ExecPollInput(
                    exec_id=exec_result.exec_id,
                    after_seq=0
                ))
                if poll_result.complete:
                    break
                await asyncio.sleep(0.1)
        finally:
            await kill(KillInput(container_id=container_id, force=True))

    benchmark(asyncio.run, run_exec())

@pytest.mark.benchmark
def test_filesystem_read_performance(benchmark):
    """Benchmark filesystem read performance."""

    async def read_file():
        # Setup
        spawn_result = await spawn(SpawnInput(image="python:3.11-slim"))
        container_id = spawn_result.container_id

        try:
            # Create test file
            test_data = b"x" * 1024 * 1024  # 1MB
            await fs_write(FileWriteInput(
                container_id=container_id,
                path="/workspace/test.bin",
                content=test_data
            ))

            # Benchmark read
            result = await fs_read(FileReadInput(
                container_id=container_id,
                path="/workspace/test.bin"
            ))
            assert len(result.content) == len(test_data)
        finally:
            await kill(KillInput(container_id=container_id, force=True))

    benchmark(asyncio.run, read_file())

# Performance regression test
def test_performance_regression():
    """Ensure performance doesn't regress beyond baseline."""
    import json
    from pathlib import Path

    baseline_path = Path("benchmarks/baseline.json")
    if not baseline_path.exists():
        pytest.skip("No baseline benchmarks found")

    with open(baseline_path) as f:
        baseline = json.load(f)

    # Current performance metrics would be compared here
    # Fail if regression > 10%
```

**Files to Create:**
- `tests/performance/test_benchmarks.py`
- `tests/performance/test_load.py`
- `benchmarks/baseline.json`

**CI Integration:**
```yaml
# .github/workflows/performance.yml
name: Performance Tests

on:
  pull_request:
    branches: [main]

jobs:
  benchmark:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync --extra dev

      - name: Run benchmarks
        run: |
          uv run pytest tests/performance/ --benchmark-json=output.json

      - name: Compare with baseline
        run: |
          uv run python scripts/compare_benchmarks.py \
            --baseline benchmarks/baseline.json \
            --current output.json \
            --threshold 10
```

**Success Criteria:**
- Baseline benchmarks established
- Performance regression tests in CI
- p95 latency < 100ms for API calls

---

#### E1-F4: Contract Testing for MCP Protocol

**Description:** Validate MCP protocol compliance.

**Implementation:**
```python
# tests/contract/test_mcp_compliance.py

import pytest
from pydantic import ValidationError

def test_all_tool_inputs_are_valid_pydantic_models():
    """Verify all MCP tool inputs are valid Pydantic models."""
    from mcp_devbench import mcp_tools
    import inspect

    for name, obj in inspect.getmembers(mcp_tools):
        if name.endswith('Input'):
            assert hasattr(obj, 'model_validate')
            assert hasattr(obj, 'model_dump')

def test_all_tool_outputs_are_valid_pydantic_models():
    """Verify all MCP tool outputs are valid Pydantic models."""
    from mcp_devbench import mcp_tools
    import inspect

    for name, obj in inspect.getmembers(mcp_tools):
        if name.endswith('Output'):
            assert hasattr(obj, 'model_validate')
            assert hasattr(obj, 'model_dump')

async def test_spawn_tool_contract():
    """Test spawn tool adheres to MCP contract."""
    # Valid input
    valid_input = SpawnInput(
        image="python:3.11-slim",
        persistent=False
    )
    result = await spawn(valid_input)

    # Output validation
    assert isinstance(result, SpawnOutput)
    assert hasattr(result, 'container_id')
    assert hasattr(result, 'status')
    assert result.status in ['running', 'created', 'stopped']

    # Invalid input should raise ValidationError
    with pytest.raises(ValidationError):
        SpawnInput(image=123)  # Invalid type

async def test_exec_streaming_contract():
    """Test exec streaming follows MCP protocol."""
    # Spawn container
    spawn_result = await spawn(SpawnInput(image="python:3.11-slim"))
    container_id = spawn_result.container_id

    try:
        # Start exec
        exec_result = await exec_start(ExecInput(
            container_id=container_id,
            cmd=["echo", "test"],
            timeout_s=5
        ))

        # Poll should return messages with sequence numbers
        poll_result = await exec_poll(ExecPollInput(
            exec_id=exec_result.exec_id,
            after_seq=0
        ))

        # Validate message structure
        for msg in poll_result.messages:
            assert hasattr(msg, 'seq')
            assert isinstance(msg.seq, int)

            if msg.complete:
                assert hasattr(msg, 'exit_code')
                assert hasattr(msg, 'usage')
            else:
                assert hasattr(msg, 'stream')
                assert msg.stream in ['stdout', 'stderr']
                assert hasattr(msg, 'data')
    finally:
        await kill(KillInput(container_id=container_id, force=True))
```

**Files to Create:**
- `tests/contract/test_mcp_compliance.py`
- `tests/contract/test_tool_schemas.py`

**Success Criteria:**
- All tools validated against MCP spec
- Schema validation in CI

---

## Epic 2: Performance Optimization

**Priority:** P0 (Critical)
**Timeline:** 2-3 weeks
**Effort:** Medium
**Owner:** Backend Team

### Features

#### E2-F1: Async Docker Client Wrapper

**Description:** Replace blocking Docker SDK with async wrapper.

**Implementation:**
```python
# src/mcp_devbench/utils/async_docker.py

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import wraps
from typing import Any, Callable, TypeVar

import docker
from docker import DockerClient

T = TypeVar('T')

class AsyncDockerClient:
    """Async wrapper around Docker SDK."""

    def __init__(self, client: DockerClient, max_workers: int = 10):
        self._client = client
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    async def _run_in_executor(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Run blocking function in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor,
            lambda: func(*args, **kwargs)
        )

    async def create_container(self, *args, **kwargs):
        """Async container creation."""
        return await self._run_in_executor(
            self._client.containers.create,
            *args,
            **kwargs
        )

    async def start_container(self, container_id: str):
        """Async container start."""
        container = self._client.containers.get(container_id)
        return await self._run_in_executor(container.start)

    async def exec_create(self, container_id: str, cmd: list, **kwargs):
        """Async exec creation."""
        container = self._client.containers.get(container_id)
        return await self._run_in_executor(
            container.exec_run,
            cmd,
            **kwargs
        )

    async def pull_image(self, image: str):
        """Async image pull."""
        return await self._run_in_executor(
            self._client.images.pull,
            image
        )

    async def ping(self) -> bool:
        """Async Docker daemon ping."""
        try:
            await self._run_in_executor(self._client.ping)
            return True
        except Exception:
            return False

    def close(self):
        """Cleanup resources."""
        self._executor.shutdown(wait=True)

# Global async client instance
_async_docker_client: AsyncDockerClient | None = None

def get_async_docker_client() -> AsyncDockerClient:
    """Get or create async Docker client."""
    global _async_docker_client

    if _async_docker_client is None:
        sync_client = get_docker_client()  # Existing sync client
        _async_docker_client = AsyncDockerClient(sync_client)

    return _async_docker_client

def close_async_docker_client():
    """Close async Docker client."""
    global _async_docker_client

    if _async_docker_client is not None:
        _async_docker_client.close()
        _async_docker_client = None
```

**Files to Create:**
- `src/mcp_devbench/utils/async_docker.py`

**Files to Modify:**
- `src/mcp_devbench/managers/container_manager.py` (use async client)
- `src/mcp_devbench/managers/exec_manager.py` (use async client)
- `src/mcp_devbench/managers/image_policy_manager.py` (use async client)

**Tests Required:**
- `tests/unit/test_async_docker.py`
- `tests/performance/test_async_vs_sync.py`

**Success Criteria:**
- All Docker operations use async wrapper
- No blocking calls in async context
- Performance improvement >30% under concurrent load

---

#### E2-F2: Database Connection Pooling

**Description:** Optimize database connection management.

**Implementation:**
```python
# src/mcp_devbench/models/database.py

async def init_db():
    """Initialize database with optimized connection pooling."""
    global _db_manager

    settings = get_settings()
    db_url = f"sqlite+aiosqlite:///{settings.state_db}"

    # Enhanced connection pooling
    engine = create_async_engine(
        db_url,
        echo=False,
        pool_size=20,              # Increased from default
        max_overflow=10,           # Allow temporary overflow
        pool_pre_ping=True,        # Verify connections before use
        pool_recycle=3600,         # Recycle connections after 1 hour
        connect_args={
            "check_same_thread": False,
            "timeout": 30,         # 30 second timeout
        },
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    _db_manager = DatabaseManager(engine)

    logger.info(
        "Database initialized with connection pooling",
        extra={
            "pool_size": 20,
            "max_overflow": 10,
            "db_url": db_url,
        }
    )
```

**Files to Modify:**
- `src/mcp_devbench/models/database.py`

**Configuration:**
```python
# src/mcp_devbench/config/settings.py

class Settings(BaseSettings):
    # ... existing fields ...

    db_pool_size: int = Field(
        default=20,
        description="Database connection pool size",
    )

    db_max_overflow: int = Field(
        default=10,
        description="Max overflow connections beyond pool size",
    )

    db_pool_recycle: int = Field(
        default=3600,
        description="Connection recycle time in seconds",
    )
```

**Success Criteria:**
- Connection pool properly configured
- No connection exhaustion under load
- Pool metrics exposed via Prometheus

---

#### E2-F3: Caching Layer for Image Resolution

**Description:** Cache image resolution results to avoid repeated Docker registry calls.

**Implementation:**
```python
# src/mcp_devbench/utils/cache.py

from functools import wraps
from typing import Any, Callable, TypeVar
from cachetools import TTLCache
import asyncio

T = TypeVar('T')

def async_cached(ttl: int = 300, maxsize: int = 128):
    """Decorator for caching async function results."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache = TTLCache(maxsize=maxsize, ttl=ttl)
        lock = asyncio.Lock()

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key
            key = str((args, tuple(sorted(kwargs.items()))))

            # Check cache
            async with lock:
                if key in cache:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cache[key]

            # Compute result
            result = await func(*args, **kwargs)

            # Store in cache
            async with lock:
                cache[key] = result

            return result

        # Add cache management methods
        wrapper.cache_info = lambda: {
            'hits': cache.currsize,
            'maxsize': cache.maxsize,
            'ttl': ttl
        }
        wrapper.cache_clear = lambda: cache.clear()

        return wrapper
    return decorator

# Usage in image_policy_manager.py
from mcp_devbench.utils.cache import async_cached

class ImagePolicyManager:

    @async_cached(ttl=3600, maxsize=100)  # Cache for 1 hour
    async def resolve_image(self, image: str) -> ResolvedImage:
        """Resolve image with caching."""
        # Existing implementation
        ...
```

**Files to Create:**
- `src/mcp_devbench/utils/cache.py`

**Files to Modify:**
- `src/mcp_devbench/managers/image_policy_manager.py`

**Dependencies:**
```toml
# pyproject.toml
dependencies = [
    # ... existing ...
    "cachetools>=5.3.0",
]
```

**Metrics:**
```python
# Add cache metrics to metrics_collector.py
def record_cache_hit(self, cache_name: str):
    self._cache_hits.labels(cache=cache_name).inc()

def record_cache_miss(self, cache_name: str):
    self._cache_misses.labels(cache=cache_name).inc()
```

**Success Criteria:**
- Image resolution cached for 1 hour
- Cache hit rate >80% in typical usage
- Cache metrics exposed

---

## Epic 3: Database & Scalability

**Priority:** P1 (High)
**Timeline:** 4-6 weeks
**Effort:** High
**Owner:** Infrastructure Team

### Features

#### E3-F1: PostgreSQL Support

**Description:** Add PostgreSQL as a production database option alongside SQLite.

**Implementation:**
```python
# src/mcp_devbench/config/settings.py

class Settings(BaseSettings):
    # Database configuration
    database_url: str = Field(
        default="sqlite+aiosqlite:///./state.db",
        description="Database connection URL (SQLite or PostgreSQL)",
    )

    # Deprecated: state_db (kept for backwards compatibility)
    state_db: str = Field(
        default="./state.db",
        description="[DEPRECATED] Path to SQLite state database",
    )

    @property
    def effective_database_url(self) -> str:
        """Get effective database URL with backwards compatibility."""
        # If database_url is explicitly set, use it
        if self.database_url != "sqlite+aiosqlite:///./state.db":
            return self.database_url

        # Otherwise, construct from state_db for backwards compatibility
        return f"sqlite+aiosqlite:///{self.state_db}"

# src/mcp_devbench/models/database.py

async def init_db():
    """Initialize database with PostgreSQL or SQLite."""
    global _db_manager

    settings = get_settings()
    db_url = settings.effective_database_url

    # Detect database type
    is_postgres = db_url.startswith("postgresql")

    # Configure connection args based on DB type
    if is_postgres:
        connect_args = {
            "server_settings": {
                "application_name": "mcp_devbench",
            }
        }
    else:
        connect_args = {
            "check_same_thread": False,
            "timeout": 30,
        }

    engine = create_async_engine(
        db_url,
        echo=False,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_recycle=settings.db_pool_recycle,
        connect_args=connect_args,
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    _db_manager = DatabaseManager(engine)

    logger.info(
        "Database initialized",
        extra={
            "db_type": "PostgreSQL" if is_postgres else "SQLite",
            "pool_size": settings.db_pool_size,
        }
    )
```

**Database-Specific Optimizations:**
```python
# src/mcp_devbench/repositories/base.py

class BaseRepository:

    async def _use_select_for_update(self) -> bool:
        """Check if SELECT FOR UPDATE is supported."""
        # PostgreSQL supports FOR UPDATE, SQLite doesn't
        engine = self.session.bind
        return "postgresql" in str(engine.url)

    async def get_with_lock(self, id: str):
        """Get entity with row lock (PostgreSQL only)."""
        if await self._use_select_for_update():
            stmt = select(self.model).where(
                self.model.id == id
            ).with_for_update()
        else:
            stmt = select(self.model).where(self.model.id == id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
```

**Alembic Migration:**
```python
# alembic/versions/add_postgres_support.py
"""Add PostgreSQL-specific indexes and constraints.

Revision ID: xxx
Revises: yyy
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add PostgreSQL-specific indexes
    connection = op.get_bind()
    if connection.dialect.name == 'postgresql':
        # Add BRIN index for time-series queries
        op.execute("""
            CREATE INDEX idx_containers_created_at_brin
            ON containers USING BRIN (created_at)
        """)

        # Add GIN index for JSONB columns (if any)
        # op.create_index(...)

def downgrade():
    connection = op.get_bind()
    if connection.dialect.name == 'postgresql':
        op.drop_index('idx_containers_created_at_brin')
```

**Documentation:**
```markdown
# docs/postgresql-setup.md

## PostgreSQL Setup

### 1. Install PostgreSQL

```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# macOS
brew install postgresql
```

### 2. Create Database

```sql
CREATE DATABASE mcp_devbench;
CREATE USER mcp_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE mcp_devbench TO mcp_user;
```

### 3. Configure MCP DevBench

```bash
export MCP_DATABASE_URL="postgresql+asyncpg://mcp_user:your_password@localhost/mcp_devbench"
```

### 4. Run Migrations

```bash
uv run alembic upgrade head
```
```

**Files to Create:**
- `docs/postgresql-setup.md`
- `alembic/versions/add_postgres_support.py`

**Files to Modify:**
- `src/mcp_devbench/config/settings.py`
- `src/mcp_devbench/models/database.py`
- `src/mcp_devbench/repositories/base.py`

**Dependencies:**
```toml
# pyproject.toml
dependencies = [
    # ... existing ...
    "asyncpg>=0.29.0",  # For PostgreSQL support
]
```

**Tests Required:**
- `tests/integration/test_postgres_backend.py`
- `tests/integration/test_sqlite_compatibility.py`

**Success Criteria:**
- Both SQLite and PostgreSQL supported
- Migrations work on both databases
- Performance tests show >2x improvement with PostgreSQL under load
- Backwards compatibility maintained

---

#### E3-F2: Distributed Locking for Multi-Instance Deployment

**Description:** Enable multiple server instances to safely share state.

**Implementation:**
```python
# src/mcp_devbench/utils/distributed_lock.py

import asyncio
from abc import ABC, abstractmethod
from typing import Any
import redis.asyncio as redis

class DistributedLock(ABC):
    """Abstract distributed lock interface."""

    @abstractmethod
    async def acquire(self, key: str, timeout: float = 10.0) -> bool:
        """Acquire lock with timeout."""
        pass

    @abstractmethod
    async def release(self, key: str) -> None:
        """Release lock."""
        pass

    @abstractmethod
    async def __aenter__(self):
        """Context manager entry."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass

class RedisDistributedLock(DistributedLock):
    """Redis-based distributed lock."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: redis.Redis | None = None
        self._lock_key: str | None = None

    async def connect(self):
        """Connect to Redis."""
        if self.client is None:
            self.client = await redis.from_url(self.redis_url)

    async def acquire(self, key: str, timeout: float = 10.0) -> bool:
        """Acquire lock with timeout."""
        await self.connect()
        self._lock_key = f"lock:{key}"

        # Try to acquire with timeout
        end_time = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < end_time:
            # Try to set lock with NX (only if not exists)
            acquired = await self.client.set(
                self._lock_key,
                "locked",
                nx=True,
                ex=int(timeout)  # Expire after timeout
            )

            if acquired:
                return True

            # Wait before retry
            await asyncio.sleep(0.1)

        return False

    async def release(self, key: str) -> None:
        """Release lock."""
        if self.client and self._lock_key:
            await self.client.delete(self._lock_key)
            self._lock_key = None

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._lock_key:
            await self.release(self._lock_key.replace("lock:", ""))

class PostgreSQLDistributedLock(DistributedLock):
    """PostgreSQL advisory lock."""

    def __init__(self, session):
        self.session = session
        self._lock_id: int | None = None

    async def acquire(self, key: str, timeout: float = 10.0) -> bool:
        """Acquire PostgreSQL advisory lock."""
        # Convert key to integer for pg_advisory_lock
        self._lock_id = hash(key) % (2**31 - 1)

        # Try to acquire lock
        result = await self.session.execute(
            sa.text(f"SELECT pg_try_advisory_lock({self._lock_id})")
        )
        acquired = result.scalar()

        return bool(acquired)

    async def release(self, key: str) -> None:
        """Release PostgreSQL advisory lock."""
        if self._lock_id is not None:
            await self.session.execute(
                sa.text(f"SELECT pg_advisory_unlock({self._lock_id})")
            )
            self._lock_id = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._lock_id:
            await self.release(str(self._lock_id))

# Factory function
def get_distributed_lock() -> DistributedLock:
    """Get distributed lock based on configuration."""
    settings = get_settings()

    if settings.redis_url:
        return RedisDistributedLock(settings.redis_url)
    elif "postgresql" in settings.database_url:
        # Use PostgreSQL advisory locks
        db_manager = get_db_manager()
        return PostgreSQLDistributedLock(db_manager.session)
    else:
        # Fallback to local lock for SQLite
        return LocalLock()

# Usage in exec_manager.py
class ExecManager:

    async def execute(self, container_id: str, cmd: list, ...) -> str:
        """Execute command with distributed concurrency control."""

        # Use distributed lock for concurrency control
        lock_key = f"exec_semaphore:{container_id}"

        async with get_distributed_lock() as lock:
            acquired = await lock.acquire(lock_key, timeout=30.0)

            if not acquired:
                raise ConcurrencyLimitExceededError(
                    f"Could not acquire execution lock for container {container_id}"
                )

            try:
                # Check current exec count across all instances
                current_count = await self._get_global_exec_count(container_id)

                if current_count >= MAX_CONCURRENT_EXECS:
                    raise ConcurrencyLimitExceededError(
                        f"Container {container_id} has reached max concurrent executions"
                    )

                # Proceed with execution
                ...
            finally:
                await lock.release(lock_key)
```

**Configuration:**
```python
# src/mcp_devbench/config/settings.py

class Settings(BaseSettings):
    # ... existing fields ...

    redis_url: str | None = Field(
        default=None,
        description="Redis URL for distributed locking (optional)",
    )
```

**Files to Create:**
- `src/mcp_devbench/utils/distributed_lock.py`

**Files to Modify:**
- `src/mcp_devbench/managers/exec_manager.py`
- `src/mcp_devbench/config/settings.py`

**Dependencies:**
```toml
# pyproject.toml
dependencies = [
    # ... existing ...
    "redis>=5.0.0",  # For distributed locking
]
```

**Tests Required:**
- `tests/integration/test_distributed_locks.py`
- `tests/integration/test_multi_instance.py`

**Success Criteria:**
- Concurrency limits enforced across multiple instances
- No race conditions in multi-instance deployment
- Performance overhead <10ms per operation

---

## Epic 4: Documentation & Developer Experience

**Priority:** P1 (High)
**Timeline:** 2 weeks
**Effort:** Low-Medium
**Owner:** Documentation Team

### Features

#### E4-F1: Comprehensive API Documentation

**Description:** Generate and publish complete API documentation.

**Implementation:**
```python
# scripts/generate_api_docs.py

from mcp_devbench import server, mcp_tools
import inspect
import json

def generate_openapi_spec():
    """Generate OpenAPI 3.0 specification."""

    spec = {
        "openapi": "3.0.0",
        "info": {
            "title": "MCP DevBench API",
            "version": "0.1.0",
            "description": "Docker container management server with MCP protocol",
            "contact": {
                "name": "MCP DevBench Team",
                "url": "https://github.com/pvliesdonk/mcp-devbench"
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT"
            }
        },
        "servers": [
            {
                "url": "http://localhost:8000",
                "description": "Development server"
            }
        ],
        "paths": {},
        "components": {
            "schemas": {},
            "securitySchemes": {
                "bearer": {
                    "type": "http",
                    "scheme": "bearer"
                },
                "oidc": {
                    "type": "openIdConnect",
                    "openIdConnectUrl": "{MCP_OAUTH_CONFIG_URL}"
                }
            }
        }
    }

    # Extract all Pydantic models
    for name, obj in inspect.getmembers(mcp_tools):
        if inspect.isclass(obj) and hasattr(obj, 'model_json_schema'):
            schema = obj.model_json_schema()
            spec["components"]["schemas"][name] = schema

    # Extract all tools
    # This would introspect the FastMCP server and extract tool definitions

    return spec

if __name__ == "__main__":
    spec = generate_openapi_spec()

    with open("docs/api/openapi.json", "w") as f:
        json.dump(spec, f, indent=2)

    print("✓ Generated docs/api/openapi.json")
```

**Documentation Structure:**
```
docs/
├── api/
│   ├── openapi.json          # OpenAPI spec
│   ├── index.md              # API overview
│   ├── authentication.md     # Auth guide
│   ├── tools/
│   │   ├── containers.md     # Container tools
│   │   ├── execution.md      # Exec tools
│   │   ├── filesystem.md     # FS tools
│   │   └── system.md         # System tools
│   └── examples/
│       ├── quickstart.md
│       ├── python-client.md
│       └── typescript-client.md
├── guides/
│   ├── getting-started.md
│   ├── deployment.md
│   ├── security.md
│   └── monitoring.md
├── operations/
│   ├── runbooks/
│   │   ├── container-cleanup.md
│   │   ├── database-recovery.md
│   │   └── performance-tuning.md
│   ├── troubleshooting.md
│   └── maintenance.md
└── development/
    ├── architecture.md
    ├── contributing.md
    ├── testing.md
    └── adrs/                  # Architecture Decision Records
        ├── 001-sqlite-choice.md
        ├── 002-repository-pattern.md
        └── 003-async-architecture.md
```

**Files to Create:**
- `scripts/generate_api_docs.py`
- `docs/api/openapi.json`
- All documentation files listed above
- `CONTRIBUTING.md`
- `SECURITY.md`

**Success Criteria:**
- Complete API reference documentation
- All tools documented with examples
- Operational runbooks for common scenarios
- Architecture Decision Records for key choices

---

#### E4-F2: Development Container Configuration

**Description:** Add devcontainer for consistent development environment.

**Implementation:**
```json
// .devcontainer/devcontainer.json
{
  "name": "MCP DevBench Development",
  "dockerFile": "Dockerfile",

  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {
      "version": "latest",
      "moby": true
    },
    "ghcr.io/devcontainers/features/python:1": {
      "version": "3.11"
    }
  },

  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "charliermarsh.ruff",
        "ms-azuretools.vscode-docker",
        "redhat.vscode-yaml",
        "GitHub.copilot"
      ],
      "settings": {
        "python.defaultInterpreterPath": "/usr/local/bin/python",
        "python.linting.enabled": true,
        "python.linting.ruffEnabled": true,
        "python.formatting.provider": "ruff",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
          "source.organizeImports": true
        }
      }
    }
  },

  "postCreateCommand": "pip install uv && uv sync --extra dev && pre-commit install",

  "forwardPorts": [8000],

  "mounts": [
    "source=/var/run/docker.sock,target=/var/run/docker.sock,type=bind"
  ],

  "remoteUser": "vscode"
}
```

```dockerfile
# .devcontainer/Dockerfile
FROM mcr.microsoft.com/devcontainers/python:3.11

# Install additional tools
RUN apt-get update && apt-get install -y \
    git \
    docker-cli \
    && rm -rf /var/lib/apt/lists/*

# Create workspace
WORKDIR /workspace
```

**Files to Create:**
- `.devcontainer/devcontainer.json`
- `.devcontainer/Dockerfile`

**Success Criteria:**
- One-click development environment setup
- All tools pre-installed and configured
- Docker-in-Docker working correctly

---

#### E4-F3: Contributing Guide

**Description:** Create comprehensive contributor documentation.

**Implementation:**
```markdown
# CONTRIBUTING.md

# Contributing to MCP DevBench

Thank you for your interest in contributing to MCP DevBench! This guide will help you get started.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Workflow](#development-workflow)
4. [Coding Standards](#coding-standards)
5. [Testing Guidelines](#testing-guidelines)
6. [Submitting Changes](#submitting-changes)
7. [Release Process](#release-process)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. Please read our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting Started

### Prerequisites

- Python 3.11+
- Docker Engine
- uv package manager
- Git

### Setting Up Development Environment

1. **Fork and clone the repository:**
   ```bash
   git fork https://github.com/pvliesdonk/mcp-devbench
   cd mcp-devbench
   ```

2. **Install dependencies:**
   ```bash
   pip install uv
   uv sync --extra dev
   ```

3. **Set up pre-commit hooks:**
   ```bash
   pre-commit install
   ```

4. **Verify setup:**
   ```bash
   uv run pytest
   uv run ruff check .
   ```

### Using Development Container (Optional)

If you use VS Code, you can use the provided devcontainer:

1. Install the "Remote - Containers" extension
2. Open the project in VS Code
3. Click "Reopen in Container" when prompted
4. Wait for the container to build and start

## Development Workflow

### Branch Strategy

- `main` - Production-ready code
- `feature/*` - New features
- `fix/*` - Bug fixes
- `docs/*` - Documentation updates
- `refactor/*` - Code refactoring

### Creating a Feature Branch

```bash
git checkout -b feature/amazing-feature
```

### Making Changes

1. Make your changes
2. Write tests for new functionality
3. Update documentation as needed
4. Run tests: `uv run pytest`
5. Check code quality: `uv run ruff check .`
6. Format code: `uv run ruff format .`

## Coding Standards

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with the following exceptions:

- Line length: 100 characters (enforced by ruff)
- Use type hints for all functions
- Prefer explicit over implicit
- Use descriptive variable names

### Code Organization

- **Repository Pattern:** All database access through repositories
- **Manager Pattern:** Business logic in manager classes
- **Dependency Injection:** Use factory functions (e.g., `get_*_manager()`)
- **Async/Await:** All I/O operations must be async

### Type Hints

All functions must have type hints:

```python
# Good
async def create_container(
    self,
    image: str,
    alias: str | None = None,
    persistent: bool = False,
) -> Container:
    ...

# Bad
async def create_container(self, image, alias=None, persistent=False):
    ...
```

### Error Handling

Use specific exception types:

```python
# Good
raise ContainerNotFoundError(f"Container {container_id} not found")

# Bad
raise Exception("Container not found")
```

### Logging

Use structured logging:

```python
# Good
logger.info(
    "Container created",
    extra={
        "container_id": container.id,
        "image": image,
    }
)

# Bad
logger.info(f"Container {container.id} created with image {image}")
```

## Testing Guidelines

### Test Structure

- **Unit Tests:** `tests/unit/`
- **Integration Tests:** `tests/integration/`
- **E2E Tests:** `tests/e2e/`
- **Performance Tests:** `tests/performance/`

### Writing Tests

All new features must include tests:

```python
import pytest
from mcp_devbench.managers.container_manager import ContainerManager

@pytest.mark.asyncio
async def test_create_container():
    """Test container creation."""
    manager = ContainerManager()

    container = await manager.create_container(
        image="alpine:latest",
        alias="test-container"
    )

    assert container.image == "alpine:latest"
    assert container.alias == "test-container"
```

### Test Coverage

- Aim for >85% code coverage
- All public APIs must have tests
- Critical paths must have integration tests

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_container_manager.py

# Run with coverage
uv run pytest --cov=mcp_devbench --cov-report=html

# Run only unit tests
uv run pytest tests/unit/

# Run with verbose output
uv run pytest -v
```

## Submitting Changes

### Commit Messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add container snapshots
fix: resolve race condition in exec manager
docs: update API documentation
refactor: simplify filesystem manager
test: add E2E tests for spawn workflow
chore: update dependencies
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code refactoring
- `test`: Tests
- `chore`: Maintenance
- `perf`: Performance improvement
- `ci`: CI/CD changes

### Pull Request Process

1. **Create PR:**
   - Write clear title using conventional commit format
   - Fill out PR template completely
   - Link related issues

2. **PR Checklist:**
   - [ ] Tests pass locally
   - [ ] Code follows style guide
   - [ ] Documentation updated
   - [ ] CHANGELOG.md updated (if needed)
   - [ ] No merge conflicts

3. **Review Process:**
   - CI must pass
   - At least one approval required
   - All comments addressed

4. **Merge:**
   - Squash and merge preferred
   - Delete branch after merge

## Release Process

Releases are automated using [Python Semantic Release](https://python-semantic-release.readthedocs.io/):

1. Merge PR to `main`
2. CI runs tests and semantic release
3. If commit triggers release:
   - Version bumped in `pyproject.toml`
   - CHANGELOG.md updated
   - Git tag created
   - Package published to PyPI
   - GitHub Release created

## Questions?

- **General questions:** [GitHub Discussions](https://github.com/pvliesdonk/mcp-devbench/discussions)
- **Bug reports:** [GitHub Issues](https://github.com/pvliesdonk/mcp-devbench/issues)
- **Security issues:** See [SECURITY.md](SECURITY.md)

Thank you for contributing! 🎉
```

**Files to Create:**
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `SECURITY.md`
- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/ISSUE_TEMPLATE/bug_report.md`
- `.github/ISSUE_TEMPLATE/feature_request.md`

**Success Criteria:**
- Complete contributing guide
- Clear development workflow documented
- PR and issue templates in place

---

## Epic 5: Advanced Security Features

**Priority:** P2 (Medium)
**Timeline:** 3-4 weeks
**Effort:** Medium-High
**Owner:** Security Team

### Features

#### E5-F1: Granular Security Policies

**Description:** Per-container security policies instead of global configuration.

**Implementation:**
```python
# src/mcp_devbench/models/security_policy.py

from pydantic import BaseModel, Field

class NetworkPolicy(BaseModel):
    """Network access policy."""
    allow_internet: bool = False
    allowed_hosts: list[str] = Field(default_factory=list)
    blocked_hosts: list[str] = Field(default_factory=list)
    allowed_ports: list[int] = Field(default_factory=list)

class ResourceLimits(BaseModel):
    """Container resource limits."""
    memory_mb: int = 512
    cpu_count: float = 1.0
    pid_limit: int = 256
    storage_mb: int | None = None

class CapabilityPolicy(BaseModel):
    """Linux capabilities policy."""
    drop_all: bool = True
    add_capabilities: list[str] = Field(default_factory=list)

class SecurityPolicy(BaseModel):
    """Complete security policy for a container."""

    # Resource limits
    resources: ResourceLimits = Field(default_factory=ResourceLimits)

    # Network policy
    network: NetworkPolicy = Field(default_factory=NetworkPolicy)

    # Capabilities
    capabilities: CapabilityPolicy = Field(default_factory=CapabilityPolicy)

    # Filesystem
    read_only_rootfs: bool = True
    tmpfs_size_mb: int = 100

    # User
    run_as_uid: int = 1000
    allow_root: bool = False

    # Security options
    no_new_privileges: bool = True
    seccomp_profile: str = "default"
    apparmor_profile: str | None = None

# Usage in spawn tool
class SpawnInput(BaseModel):
    image: str
    persistent: bool = False
    alias: str | None = None
    ttl_s: int | None = None
    idempotency_key: str | None = None
    security_policy: SecurityPolicy | None = None  # NEW

# Implementation in container_manager.py
async def create_container(
    self,
    image: str,
    alias: str | None = None,
    persistent: bool = False,
    ttl_s: int | None = None,
    security_policy: SecurityPolicy | None = None,
) -> Container:
    """Create container with custom security policy."""

    # Use provided policy or default
    policy = security_policy or SecurityPolicy()

    # Apply policy to container creation
    host_config = {
        # Resources
        "mem_limit": f"{policy.resources.memory_mb}m",
        "nano_cpus": int(policy.resources.cpu_count * 1e9),
        "pids_limit": policy.resources.pid_limit,

        # Network
        "network_mode": "none" if not policy.network.allow_internet else "bridge",

        # Security
        "cap_drop": ["ALL"] if policy.capabilities.drop_all else [],
        "cap_add": policy.capabilities.add_capabilities,
        "read_only": policy.read_only_rootfs,
        "security_opt": [
            "no-new-privileges:true" if policy.no_new_privileges else "no-new-privileges:false",
        ],
    }

    # Add seccomp profile
    if policy.seccomp_profile:
        host_config["security_opt"].append(f"seccomp={policy.seccomp_profile}")

    # Add AppArmor profile
    if policy.apparmor_profile:
        host_config["security_opt"].append(f"apparmor={policy.apparmor_profile}")

    # Create container with policy
    docker_container = await self.async_docker.create_container(
        image=actual_image,
        user=policy.run_as_uid,
        host_config=host_config,
        ...
    )
```

**Files to Create:**
- `src/mcp_devbench/models/security_policy.py`

**Files to Modify:**
- `src/mcp_devbench/mcp_tools.py` (add security_policy to SpawnInput)
- `src/mcp_devbench/managers/container_manager.py`
- `src/mcp_devbench/managers/security_manager.py`

**Tests Required:**
- `tests/unit/test_security_policies.py`
- `tests/integration/test_network_policies.py`

**Success Criteria:**
- Per-container security policies work
- Network isolation enforced
- Resource limits respected
- Audit logs record policy usage

---

#### E5-F2: Container Image Scanning

**Description:** Scan container images for vulnerabilities before allowing spawn.

**Implementation:**
```python
# src/mcp_devbench/managers/image_scanner.py

import asyncio
import json
from typing import Literal

class VulnerabilitySeverity:
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"

class Vulnerability(BaseModel):
    """Container image vulnerability."""
    id: str
    severity: str
    title: str
    description: str
    package: str
    installed_version: str
    fixed_version: str | None = None

class ScanResult(BaseModel):
    """Image scan result."""
    image: str
    scanned_at: datetime
    vulnerabilities: list[Vulnerability]
    passed: bool

    @property
    def critical_count(self) -> int:
        return len([v for v in self.vulnerabilities if v.severity == "CRITICAL"])

    @property
    def high_count(self) -> int:
        return len([v for v in self.vulnerabilities if v.severity == "HIGH"])

class ImageScanner:
    """Scan container images for vulnerabilities."""

    def __init__(self):
        self.settings = get_settings()
        self.enabled = self.settings.image_scanning_enabled
        self.max_severity = self.settings.image_scan_max_severity

    async def scan_image(self, image: str) -> ScanResult:
        """Scan image using Trivy."""

        if not self.enabled:
            # Scanning disabled, return empty result
            return ScanResult(
                image=image,
                scanned_at=datetime.now(timezone.utc),
                vulnerabilities=[],
                passed=True
            )

        # Run Trivy scan
        cmd = [
            "trivy",
            "image",
            "--format", "json",
            "--severity", "HIGH,CRITICAL",
            "--quiet",
            image
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"Trivy scan failed: {stderr.decode()}")
            raise ImageScanError(f"Failed to scan image {image}")

        # Parse results
        trivy_results = json.loads(stdout.decode())
        vulnerabilities = self._parse_trivy_results(trivy_results)

        # Determine if scan passed
        passed = self._check_scan_passed(vulnerabilities)

        return ScanResult(
            image=image,
            scanned_at=datetime.now(timezone.utc),
            vulnerabilities=vulnerabilities,
            passed=passed
        )

    def _parse_trivy_results(self, trivy_results: dict) -> list[Vulnerability]:
        """Parse Trivy JSON output."""
        vulns = []

        for result in trivy_results.get("Results", []):
            for vuln in result.get("Vulnerabilities", []):
                vulns.append(Vulnerability(
                    id=vuln.get("VulnerabilityID"),
                    severity=vuln.get("Severity"),
                    title=vuln.get("Title", ""),
                    description=vuln.get("Description", ""),
                    package=vuln.get("PkgName", ""),
                    installed_version=vuln.get("InstalledVersion", ""),
                    fixed_version=vuln.get("FixedVersion")
                ))

        return vulns

    def _check_scan_passed(self, vulnerabilities: list[Vulnerability]) -> bool:
        """Check if scan passed based on max severity."""

        severity_levels = {
            "LOW": 1,
            "MEDIUM": 2,
            "HIGH": 3,
            "CRITICAL": 4
        }

        max_allowed = severity_levels.get(self.max_severity, 4)

        for vuln in vulnerabilities:
            vuln_level = severity_levels.get(vuln.severity, 0)
            if vuln_level >= max_allowed:
                return False

        return True

# Integration in image_policy_manager.py
class ImagePolicyManager:

    def __init__(self):
        # ... existing ...
        self.scanner = ImageScanner()

    async def resolve_image(self, image: str) -> ResolvedImage:
        """Resolve and scan image."""

        # Existing resolution logic
        resolved = await self._resolve_image_reference(image)

        # Scan image if enabled
        if self.scanner.enabled:
            scan_result = await self.scanner.scan_image(resolved.resolved_ref)

            if not scan_result.passed:
                logger.warning(
                    "Image failed security scan",
                    extra={
                        "image": image,
                        "critical": scan_result.critical_count,
                        "high": scan_result.high_count,
                    }
                )

                raise ImageSecurityError(
                    f"Image {image} failed security scan: "
                    f"{scan_result.critical_count} critical, "
                    f"{scan_result.high_count} high severity vulnerabilities"
                )

            logger.info(
                "Image passed security scan",
                extra={
                    "image": image,
                    "vulnerabilities": len(scan_result.vulnerabilities),
                }
            )

        return resolved
```

**Configuration:**
```python
# src/mcp_devbench/config/settings.py

class Settings(BaseSettings):
    # ... existing ...

    image_scanning_enabled: bool = Field(
        default=False,
        description="Enable container image vulnerability scanning",
    )

    image_scan_max_severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        default="HIGH",
        description="Maximum allowed vulnerability severity",
    )
```

**Files to Create:**
- `src/mcp_devbench/managers/image_scanner.py`

**Files to Modify:**
- `src/mcp_devbench/managers/image_policy_manager.py`
- `src/mcp_devbench/config/settings.py`
- `src/mcp_devbench/utils/exceptions.py` (add ImageSecurityError)

**Prerequisites:**
- Trivy must be installed in the Docker container

**Tests Required:**
- `tests/unit/test_image_scanner.py`
- `tests/integration/test_scan_workflow.py`

**Success Criteria:**
- Images scanned before spawning
- Configurable severity thresholds
- Scan results logged and audited
- Cache scan results to avoid re-scanning

---

## Epic 6: Advanced Features

**Priority:** P2 (Medium)
**Timeline:** 4 weeks
**Effort:** High
**Owner:** Feature Team

### Features

#### E6-F1: Container Stats and Resource Monitoring

**Description:** Real-time container resource metrics.

**Implementation:**
```python
# src/mcp_devbench/mcp_tools.py

class ContainerStatsOutput(BaseModel):
    """Container resource statistics."""
    container_id: str
    cpu_percent: float
    memory_usage_mb: float
    memory_limit_mb: float
    memory_percent: float
    network_rx_bytes: int
    network_tx_bytes: int
    block_read_bytes: int
    block_write_bytes: int
    pids: int
    timestamp: datetime

# src/mcp_devbench/server.py

@mcp.tool()
async def container_stats(input_data: ContainerStatsInput) -> ContainerStatsOutput:
    """Get real-time container resource statistics."""

    manager = ContainerStatsManager()
    stats = await manager.get_stats(input_data.container_id)

    return ContainerStatsOutput(**stats)

# src/mcp_devbench/managers/container_stats_manager.py

class ContainerStatsManager:
    """Manage container resource monitoring."""

    async def get_stats(self, container_id: str) -> dict:
        """Get container stats from Docker."""

        # Get container
        async with get_db_manager().get_session() as session:
            repo = ContainerRepository(session)
            container = await repo.get(container_id)

            if not container:
                raise ContainerNotFoundError(container_id)

        # Get Docker container
        docker_client = get_async_docker_client()
        docker_container = await docker_client.get_container(container.docker_id)

        # Get stats (stream=False for single reading)
        stats = await docker_client.get_stats(container.docker_id, stream=False)

        # Parse stats
        cpu_percent = self._calculate_cpu_percent(stats)
        memory_usage = stats["memory_stats"]["usage"]
        memory_limit = stats["memory_stats"]["limit"]
        memory_percent = (memory_usage / memory_limit) * 100 if memory_limit > 0 else 0

        # Network stats
        networks = stats.get("networks", {})
        network_rx = sum(net["rx_bytes"] for net in networks.values())
        network_tx = sum(net["tx_bytes"] for net in networks.values())

        # Block I/O stats
        blkio = stats.get("blkio_stats", {}).get("io_service_bytes_recursive", [])
        block_read = sum(entry["value"] for entry in blkio if entry["op"] == "Read")
        block_write = sum(entry["value"] for entry in blkio if entry["op"] == "Write")

        # PIDs
        pids = stats.get("pids_stats", {}).get("current", 0)

        return {
            "container_id": container_id,
            "cpu_percent": cpu_percent,
            "memory_usage_mb": memory_usage / 1024 / 1024,
            "memory_limit_mb": memory_limit / 1024 / 1024,
            "memory_percent": memory_percent,
            "network_rx_bytes": network_rx,
            "network_tx_bytes": network_tx,
            "block_read_bytes": block_read,
            "block_write_bytes": block_write,
            "pids": pids,
            "timestamp": datetime.now(timezone.utc),
        }

    def _calculate_cpu_percent(self, stats: dict) -> float:
        """Calculate CPU percentage from Docker stats."""
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                    stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                       stats["precpu_stats"]["system_cpu_usage"]
        cpu_count = stats["cpu_stats"].get("online_cpus", 1)

        if system_delta > 0 and cpu_delta > 0:
            return (cpu_delta / system_delta) * cpu_count * 100.0
        return 0.0
```

**Files to Create:**
- `src/mcp_devbench/managers/container_stats_manager.py`

**Files to Modify:**
- `src/mcp_devbench/mcp_tools.py`
- `src/mcp_devbench/server.py`
- `src/mcp_devbench/utils/async_docker.py` (add get_stats method)

**Tests Required:**
- `tests/unit/test_container_stats.py`
- `tests/integration/test_stats_monitoring.py`

**Success Criteria:**
- Real-time stats retrieval
- Accurate CPU and memory calculations
- Network and I/O metrics included

---

#### E6-F2: Workspace Snapshots

**Description:** Save and restore container workspace state.

**Implementation:**
```python
# src/mcp_devbench/mcp_tools.py

class SnapshotInput(BaseModel):
    """Create workspace snapshot."""
    container_id: str
    snapshot_name: str
    description: str | None = None

class SnapshotOutput(BaseModel):
    """Snapshot creation result."""
    snapshot_id: str
    image_tag: str
    size_mb: float

class SpawnFromSnapshotInput(BaseModel):
    """Spawn from snapshot."""
    snapshot_id: str
    persistent: bool = False
    alias: str | None = None

# src/mcp_devbench/managers/snapshot_manager.py

class SnapshotManager:
    """Manage container workspace snapshots."""

    async def create_snapshot(
        self,
        container_id: str,
        snapshot_name: str,
        description: str | None = None
    ) -> dict:
        """Create snapshot by committing container."""

        # Get container
        async with get_db_manager().get_session() as session:
            repo = ContainerRepository(session)
            container = await repo.get(container_id)

            if not container:
                raise ContainerNotFoundError(container_id)

        # Generate snapshot ID and image tag
        snapshot_id = f"snap_{uuid4()}"
        image_tag = f"mcp-devbench/snapshot:{snapshot_name}"

        # Commit container to image
        docker_client = get_async_docker_client()
        new_image = await docker_client.commit_container(
            container.docker_id,
            repository="mcp-devbench/snapshot",
            tag=snapshot_name,
            message=description or f"Snapshot of {container_id}"
        )

        # Store snapshot metadata in database
        snapshot = Snapshot(
            id=snapshot_id,
            container_id=container_id,
            image_tag=image_tag,
            name=snapshot_name,
            description=description,
            created_at=datetime.now(timezone.utc),
            size_bytes=new_image.attrs["Size"]
        )

        async with get_db_manager().get_session() as session:
            snapshot_repo = SnapshotRepository(session)
            await snapshot_repo.create(snapshot)

        # Audit log
        audit_logger = get_audit_logger()
        audit_logger.log_event(
            AuditEventType.SNAPSHOT_CREATE,
            snapshot_id=snapshot_id,
            container_id=container_id,
            details={"name": snapshot_name}
        )

        logger.info(
            "Snapshot created",
            extra={
                "snapshot_id": snapshot_id,
                "container_id": container_id,
                "image_tag": image_tag,
            }
        )

        return {
            "snapshot_id": snapshot_id,
            "image_tag": image_tag,
            "size_mb": new_image.attrs["Size"] / 1024 / 1024,
        }

    async def spawn_from_snapshot(
        self,
        snapshot_id: str,
        persistent: bool = False,
        alias: str | None = None
    ) -> Container:
        """Spawn new container from snapshot."""

        # Get snapshot
        async with get_db_manager().get_session() as session:
            snapshot_repo = SnapshotRepository(session)
            snapshot = await snapshot_repo.get(snapshot_id)

            if not snapshot:
                raise SnapshotNotFoundError(snapshot_id)

        # Create container from snapshot image
        container_manager = ContainerManager()
        container = await container_manager.create_container(
            image=snapshot.image_tag,
            alias=alias,
            persistent=persistent
        )

        # Start container
        await container_manager.start_container(container.id)

        # Audit log
        audit_logger = get_audit_logger()
        audit_logger.log_event(
            AuditEventType.SNAPSHOT_SPAWN,
            snapshot_id=snapshot_id,
            container_id=container.id,
        )

        return container

# Database model
class Snapshot(Base):
    """Container workspace snapshot."""
    __tablename__ = "snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    container_id: Mapped[str] = mapped_column(String, ForeignKey("containers.id"))
    image_tag: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    size_bytes: Mapped[int] = mapped_column(Integer)
```

**Files to Create:**
- `src/mcp_devbench/managers/snapshot_manager.py`
- `src/mcp_devbench/models/snapshots.py`
- `src/mcp_devbench/repositories/snapshots.py`
- `alembic/versions/add_snapshots_table.py`

**Files to Modify:**
- `src/mcp_devbench/mcp_tools.py`
- `src/mcp_devbench/server.py`
- `src/mcp_devbench/utils/async_docker.py` (add commit_container method)

**Tests Required:**
- `tests/unit/test_snapshot_manager.py`
- `tests/integration/test_snapshot_workflow.py`

**Success Criteria:**
- Snapshots created from containers
- New containers spawned from snapshots
- Snapshot metadata stored in database
- Audit logging for snapshot operations

---

## Priority Matrix

| Epic | Priority | Impact | Effort | Timeline | Dependencies |
|------|----------|--------|--------|----------|--------------|
| **Quick Wins** | P0 | High | Low | 1-2 weeks | None |
| **Epic 1: Testing** | P0 | High | Medium | 3-4 weeks | Quick Wins |
| **Epic 2: Performance** | P0 | High | Medium | 2-3 weeks | Quick Wins |
| **Epic 3: Database** | P1 | High | High | 4-6 weeks | E2-F1 |
| **Epic 4: Documentation** | P1 | Medium | Low | 2 weeks | None |
| **Epic 5: Security** | P2 | High | Medium | 3-4 weeks | E2-F1 |
| **Epic 6: Features** | P2 | Medium | High | 4 weeks | E2-F1, E3-F1 |

---

## Implementation Guidelines

### For Coding Agents

When implementing features from this roadmap:

1. **Read the Feature Description** - Understand the problem and proposed solution
2. **Review Implementation Code** - Examine the provided code examples
3. **Create/Modify Files** - Follow the "Files to Create/Modify" section
4. **Add Dependencies** - Update pyproject.toml if new packages needed
5. **Write Tests** - Implement tests from "Tests Required" section
6. **Update Documentation** - Document new features in appropriate docs
7. **Run Quality Checks:**
   ```bash
   uv run ruff check .
   uv run ruff format .
   uv run pytest
   ```
8. **Commit with Conventional Commits:**
   ```bash
   git commit -m "feat: add idempotency to spawn tool"
   ```

### Testing Strategy

- **Unit Tests:** Test individual components in isolation
- **Integration Tests:** Test component interactions
- **E2E Tests:** Test complete workflows
- **Performance Tests:** Benchmark critical paths

### Code Review Checklist

- [ ] Follows existing code patterns (Repository, Manager, DI)
- [ ] All functions have type hints
- [ ] Comprehensive error handling
- [ ] Structured logging for all operations
- [ ] Tests added with >85% coverage
- [ ] Documentation updated
- [ ] No blocking I/O in async functions
- [ ] Security implications considered

---

## Conclusion

This roadmap provides a clear, prioritized path for evolving MCP DevBench from v0.1 to an enterprise-grade platform. By focusing on Quick Wins first, then systematically addressing Testing, Performance, and Scalability, the project can maintain momentum while building a solid foundation for advanced features.

Each epic and feature is designed to be implemented incrementally by coding agents, with clear specifications, code examples, and success criteria.

**Next Steps:**
1. Review and approve roadmap
2. Set up project tracking (GitHub Projects)
3. Begin with Quick Wins (1-2 weeks)
4. Proceed to Epic 1 (Testing) and Epic 2 (Performance) in parallel
5. Regular progress reviews and roadmap adjustments
