# Contributing to MCP DevBench

Thank you for your interest in contributing to MCP DevBench! This guide will help you get started.

## Quick Links

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Guidelines](#testing-guidelines)
- [Submitting Changes](#submitting-changes)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful and professional in all interactions.

## Getting Started

### Prerequisites

- Python 3.11+
- Docker Engine
- uv package manager
- Git

### Setting Up Development Environment

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/mcp-devbench
   cd mcp-devbench
   ```

2. **Install dependencies:**
   ```bash
   pip install uv
   uv sync --extra dev
   ```

3. **Set up pre-commit hooks:**
   ```bash
   uv run pre-commit install
   ```

4. **Verify setup:**
   ```bash
   uv run pytest
   uv run ruff check .
   ```

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
7. Type check: `uv run pyright src/`

## Coding Standards

We follow strict coding standards to maintain code quality. Please refer to our [Project Style Guide](docs/development/project-style.md) for detailed conventions.

### Key Points

- **Use uv for package management** - Not pip
- **Follow PEP 8** with 100 character line limit
- **Type hints required** for all functions
- **Async/await** for all I/O operations
- **Structured logging** over print statements
- **Specific exceptions** instead of generic Exception

### Code Organization

- **Repository Pattern:** All database access through repositories
- **Manager Pattern:** Business logic in manager classes
- **Dependency Injection:** Use factory functions (e.g., `get_*_manager()`)
- **Async/Await:** All I/O operations must be async

## Testing Guidelines

### Test Structure

- **Unit Tests:** `tests/unit/`
- **Integration Tests:** `tests/integration/`
- **E2E Tests:** `tests/e2e/` (if applicable)

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
   - [ ] Type checking passes
   - [ ] No merge conflicts

3. **Review Process:**
   - CI must pass
   - At least one approval required
   - All comments addressed

4. **Merge:**
   - Squash and merge preferred
   - Delete branch after merge

## Development Tips

### Pre-commit Hooks

Pre-commit hooks run automatically before each commit:

```bash
# Install hooks
uv run pre-commit install

# Run manually
uv run pre-commit run --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

### Running the Server Locally

```bash
# Run the MCP server
uv run python -m mcp_devbench.server

# With custom config
export MCP_DOCKER_HOST=unix:///var/run/docker.sock
uv run python -m mcp_devbench.server
```

### Debugging Tests

```bash
# Run with verbose output
uv run pytest -v -s

# Run specific test with debugging
uv run pytest tests/unit/test_container_manager.py::test_create_container -v -s

# Stop on first failure
uv run pytest -x
```

## Questions?

- **General questions:** [GitHub Discussions](https://github.com/pvliesdonk/mcp-devbench/discussions)
- **Bug reports:** [GitHub Issues](https://github.com/pvliesdonk/mcp-devbench/issues)
- **Security issues:** Please report privately (see SECURITY.md)

## License

By contributing, you agree that your contributions will be licensed under the same license as the project (MIT License).

Thank you for contributing! 🎉
