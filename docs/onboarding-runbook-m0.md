# Dev Onboarding (M0) — FastMCP2 HTTP default

## Prereqs
- Docker available (e.g., `/var/run/docker.sock`)
- Python 3.11+
- `uv` installed: https://docs.astral.sh/uv/

## Setup
```bash
git clone https://github.com/pvliesdonk/mcp-devbench
cd mcp-devbench
cp .env.example .env
uv sync --all-extras --dev
uv run pre-commit install
```

## Run (HTTP transport default)
```bash
uv run app/main.py
```

## Call the MCP tool
- Tool: `ensure_default()`
- Resource: `default_container`

> In M0 we use HTTP; STDIO is available if you set `MCP_TRANSPORT=stdio`.

## Notes
- Metrics/health endpoints are deferred; rely on audit logs and tool success.
