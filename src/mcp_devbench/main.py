"""Entrypoint for the FastMCP2 server.

- HTTP default; STDIO fallback via env.
- Boot reconciliation before serving.
"""
from __future__ import annotations
from mcp_devbench.mcp_server import mcp, boot_reconcile
from mcp_devbench.config import settings


def run() -> None:
    boot_reconcile()
    if settings.mcp_transport == "http":
        mcp.run_http(settings.mcp_http_host, settings.mcp_http_port)
    else:
        mcp.run_stdio()


if __name__ == "__main__":
    run()
