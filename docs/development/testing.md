# Testing

Testing guide for MCP DevBench.

## Running Tests

```bash
# All tests
uv run pytest

# With coverage
uv run pytest --cov=mcp_devbench --cov-report=html

# Specific test
uv run pytest tests/unit/test_container_manager.py

# By marker
uv run pytest -m "not e2e"
```

## Test Structure

```
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests
├── e2e/           # End-to-end tests
└── fixtures/      # Test fixtures
```

## Writing Tests

```python
import pytest
from mcp_devbench.managers import ContainerManager

@pytest.mark.asyncio
async def test_create_container():
    manager = ContainerManager()
    container = await manager.create_container(
        image="python:3.11-slim"
    )
    assert container.image == "python:3.11-slim"
```

## Test Coverage

Target: >85% coverage

Check coverage:
```bash
uv run pytest --cov --cov-report=term-missing
```

## Next Steps

- [Contributing](contributing.md)
- [Architecture](architecture.md)
