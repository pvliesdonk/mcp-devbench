# MCP DevBench

MCP DevBench is a Docker container management server that implements the Model Context Protocol (MCP) for managing development environments. It provides isolated, persistent workspaces with secure command execution and filesystem operations.

## Features

- **Container Lifecycle Management**: Create, start, stop, and remove Docker containers
- **MCP Protocol Integration**: Full MCP server implementation with typed Pydantic models
- **State Management**: SQLite-based state persistence with SQLAlchemy
- **Configuration Management**: Environment-based configuration with Pydantic Settings
- **Structured Logging**: JSON-formatted logging for production observability
- **Docker Integration**: Secure Docker daemon communication with connection pooling

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
| `MCP_STATE_DB` | `./state.db` | Path to SQLite state database |
| `MCP_DRAIN_GRACE_S` | `60` | Grace period in seconds for draining operations during shutdown |
| `MCP_TRANSIENT_GC_DAYS` | `7` | Days to keep transient containers before garbage collection |
| `MCP_DOCKER_HOST` | (auto-detect) | Docker daemon host URL |
| `MCP_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `MCP_LOG_FORMAT` | `json` | Log format (json or text) |
| `MCP_HOST` | `0.0.0.0` | Server host to bind to |
| `MCP_PORT` | `8000` | Server port to bind to |

### Example .env file
```bash
MCP_ALLOWED_REGISTRIES=docker.io,ghcr.io,registry.example.com
MCP_STATE_DB=/data/state.db
MCP_LOG_LEVEL=DEBUG
MCP_LOG_FORMAT=json
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

This project is currently implementing **Epic 1: Foundation Layer**:

- [x] Feature 1.1: Project Scaffold & Configuration
- [ ] Feature 1.2: State Store & Schema
- [ ] Feature 1.3: Docker Container Lifecycle Manager

See [mcp-devbench-work-breakdown.md](mcp-devbench-work-breakdown.md) for the complete implementation roadmap.

## License

See [LICENSE](LICENSE) for details.

## Contributing

This project is currently in active development. Contributions are welcome once the foundation layer is complete.
