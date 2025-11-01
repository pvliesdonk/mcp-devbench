# Installation

This guide walks you through installing MCP DevBench on your system.

## Prerequisites

Before installing MCP DevBench, ensure you have:

- **Python 3.11 or higher** - [Download Python](https://www.python.org/downloads/)
- **Docker Engine** - [Install Docker](https://docs.docker.com/get-docker/)
- **uv package manager** - Fast Python package installer

## Installing uv

[uv](https://github.com/astral-sh/uv) is the recommended package manager for MCP DevBench. It's significantly faster than pip and provides better dependency resolution.

```bash
pip install uv
```

## Installation Methods

### From Source (Recommended for Development)

1. **Clone the repository:**

```bash
git clone https://github.com/pvliesdonk/mcp-devbench.git
cd mcp-devbench
```

2. **Install dependencies:**

```bash
uv sync
```

This creates a virtual environment in `.venv/` and installs all dependencies.

3. **Verify installation:**

```bash
uv run python -m mcp_devbench.server --version
```

### Using Docker

1. **Pull the pre-built image:**

```bash
docker pull ghcr.io/pvliesdonk/mcp-devbench:latest
```

Or **build locally:**

```bash
docker build -t mcp-devbench .
```

2. **Verify installation:**

```bash
docker run --rm mcp-devbench --version
```

### Using Docker Compose

1. **Create `docker-compose.yml`:**

```yaml
version: '3.8'

services:
  mcp-devbench:
    image: ghcr.io/pvliesdonk/mcp-devbench:latest
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    ports:
      - "8000:8000"
    environment:
      MCP_TRANSPORT_MODE: streamable-http
      MCP_HOST: 0.0.0.0
      MCP_PORT: 8000
      MCP_AUTH_MODE: none
```

2. **Start the service:**

```bash
docker-compose up -d
```

## Development Installation

If you plan to contribute to MCP DevBench, install with development dependencies:

```bash
uv sync --extra dev
```

This installs additional tools:
- pytest (testing)
- ruff (linting and formatting)
- pyright (type checking)
- pre-commit (git hooks)

Set up pre-commit hooks:

```bash
uv run pre-commit install
```

## Verify Installation

Test that MCP DevBench is working:

```bash
# Run in stdio mode
uv run python -m mcp_devbench.server

# In another terminal, test with a simple MCP client
# (The server will exit when the client disconnects)
```

You should see startup logs indicating the server is ready.

## Next Steps

- **[Quick Start Guide](quickstart.md)** - Learn the basics
- **[Configuration](configuration.md)** - Configure MCP DevBench for your needs
- **[User Guide](../guide/containers.md)** - Deep dive into features

## Troubleshooting

### Docker Socket Permission Denied

If you get a permission error accessing `/var/run/docker.sock`:

```bash
# Add your user to the docker group
sudo usermod -aG docker $USER

# Log out and back in for changes to take effect
```

### uv command not found

Make sure uv is installed and in your PATH:

```bash
pip install --user uv
export PATH="$HOME/.local/bin:$PATH"
```

### Python Version Issues

MCP DevBench requires Python 3.11+. Check your version:

```bash
python --version
```

If you have an older version, install Python 3.11+ from [python.org](https://www.python.org/downloads/).

For more troubleshooting help, see the [Troubleshooting Guide](../operations/troubleshooting.md).
