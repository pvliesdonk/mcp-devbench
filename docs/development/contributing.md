# Contributing

Thank you for contributing to MCP DevBench!

## Quick Start

```bash
# Clone repository
git clone https://github.com/pvliesdonk/mcp-devbench.git
cd mcp-devbench

# Install dependencies
pip install uv
uv sync --extra dev

# Install pre-commit hooks
uv run pre-commit install

# Run tests
uv run pytest
```

## Development Workflow

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write tests
5. Run quality checks
6. Submit a pull request

## Code Quality

```bash
# Format code
uv run ruff format .

# Lint code
uv run ruff check .

# Type check
uv run pyright src/

# Run tests
uv run pytest --cov
```

## Pull Request Guidelines

- Write clear commit messages
- Add tests for new features
- Update documentation
- Ensure CI passes

See [CONTRIBUTING.md](https://github.com/pvliesdonk/mcp-devbench/blob/main/CONTRIBUTING.md) for details.
