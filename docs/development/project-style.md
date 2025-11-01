# Project Style Guide

## Package Management

**Standard: uv (not pip)**

MCP DevBench uses [uv](https://github.com/astral-sh/uv) as the standard package manager.

**✅ Do:**
```bash
# Install dependencies
uv sync

# Add a dependency
uv add requests

# Add a dev dependency
uv add --dev pytest

# Run commands in the virtual environment
uv run pytest
uv run python -m mcp_devbench.server

# Install the project in development mode
uv pip install -e .
```

**❌ Don't:**
```bash
# Avoid using pip directly
pip install -r requirements.txt  # Don't do this
pip install requests             # Don't do this
python -m pytest                 # Use 'uv run pytest' instead
```

**Why uv?**
- **10-100x faster** than pip for dependency resolution
- **Built-in lock file** for reproducible installs
- **Compatible with pip** - uses standard pyproject.toml
- **Better caching** and parallel downloads
- **Active development** by Astral (creators of ruff)

### Virtual Environment

uv automatically manages the virtual environment in `.venv/`. You don't need to manually create or activate it.

```bash
# uv automatically uses .venv/
uv run python --version

# If you need to activate manually (rare):
source .venv/bin/activate  # Unix
.venv\Scripts\activate     # Windows
```

### Dependencies

**Adding Dependencies:**

1. **Runtime dependencies** go in `pyproject.toml` under `[project.dependencies]`:
   ```bash
   uv add fastmcp pydantic docker
   ```

2. **Development dependencies** go in `[project.optional-dependencies.dev]`:
   ```bash
   uv add --dev pytest ruff pyright
   ```

3. **Always commit `uv.lock`** - This ensures reproducible builds across all environments.

**Updating Dependencies:**

```bash
# Update all dependencies
uv sync --upgrade

# Update specific package
uv add requests@latest
```

## Code Style

**Linting and Formatting: ruff**

```bash
# Check code style
uv run ruff check .

# Auto-fix issues
uv run ruff check . --fix

# Format code
uv run ruff format .
```

**Type Checking: pyright**

```bash
# Run type checker
uv run pyright src/

# Type check specific file
uv run pyright src/mcp_devbench/server.py
```

**Pre-commit Hooks:**

Set up pre-commit hooks to automatically check code before committing:

```bash
# Install pre-commit hooks
uv run pre-commit install

# Manually run on all files
uv run pre-commit run --all-files
```

## Testing

**Running Tests:**

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=mcp_devbench --cov-report=html

# Run specific test file
uv run pytest tests/unit/test_container_manager.py

# Run with specific markers
uv run pytest -m "not e2e"  # Skip E2E tests
uv run pytest -m integration  # Only integration tests
```

## Import Organization

**Order:**
1. Standard library imports
2. Third-party imports
3. Local application imports

```python
# Good
import asyncio
import json
from datetime import datetime

from docker import DockerClient
from pydantic import BaseModel

from mcp_devbench.config import get_settings
from mcp_devbench.utils import get_logger
```

**Avoid star imports:**

```python
# ❌ Bad
from mcp_devbench.models import *

# ✅ Good
from mcp_devbench.models import Container, Exec, Attachment
```

## Async Conventions

**Always use async for I/O operations:**

```python
# ✅ Good
async def read_file(path: str) -> bytes:
    return await asyncio.to_thread(lambda: open(path, 'rb').read())

# ❌ Bad
def read_file(path: str) -> bytes:
    return open(path, 'rb').read()  # Blocks event loop!
```

**Use type hints everywhere:**

```python
# ✅ Good
async def create_container(
    image: str,
    alias: str | None = None,
    persistent: bool = False,
) -> Container:
    ...

# ❌ Bad
async def create_container(image, alias=None, persistent=False):
    ...
```

## Error Handling

**Use specific exceptions:**

```python
# ✅ Good
from mcp_devbench.utils.exceptions import ContainerNotFoundError

if not container:
    raise ContainerNotFoundError(f"Container {container_id} not found")

# ❌ Bad
if not container:
    raise Exception("Container not found")
```

## Logging

**Use structured logging:**

```python
# ✅ Good
logger.info(
    "Container created",
    extra={
        "container_id": container.id,
        "image": container.image,
    }
)

# ❌ Bad
logger.info(f"Container {container.id} created with image {container.image}")
```

## Commit Messages

**Use Conventional Commits:**

```bash
# Format: <type>(<scope>): <description>

feat(exec): add idempotency support for command execution
fix(fs): resolve race condition in concurrent writes
docs(api): add OpenAPI specification
refactor(db): optimize connection pooling
test(e2e): add full workflow integration tests
chore(deps): update dependencies
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements
- `ci`: CI/CD changes

## Documentation

**Docstrings:**

Use Google-style docstrings:

```python
async def create_container(
    image: str,
    alias: str | None = None,
    persistent: bool = False,
) -> Container:
    """Create a new Docker container.

    Args:
        image: Docker image reference (e.g., "python:3.11-slim")
        alias: Optional user-friendly name for the container
        persistent: Whether container should persist across restarts

    Returns:
        Created container instance

    Raises:
        ContainerAlreadyExistsError: If alias already exists
        ImagePolicyError: If image is not allowed
        DockerAPIError: If Docker operations fail
    """
    ...
```

## CI/CD

All checks must pass before merging:

1. ✅ Tests pass (`uv run pytest`)
2. ✅ Linting passes (`uv run ruff check .`)
3. ✅ Formatting correct (`uv run ruff format --check .`)
4. ✅ Type checking passes (`uv run pyright src/`)
5. ✅ Security scans pass (Trivy)
6. ✅ Code coverage >85%

## Summary

| Tool | Purpose | Command |
|------|---------|---------|
| **uv** | Package management | `uv sync`, `uv add`, `uv run` |
| **ruff** | Linting + Formatting | `uv run ruff check .`, `uv run ruff format .` |
| **pyright** | Type checking | `uv run pyright src/` |
| **pytest** | Testing | `uv run pytest` |
| **pre-commit** | Git hooks | `uv run pre-commit run --all-files` |
