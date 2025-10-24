"""main.py — process entrypoint for the FastMCP2 server.

- Defaults to HTTP transport bound to MCP_HTTP_HOST:MCP_HTTP_PORT.
- Supports STDIO fallback by setting MCP_TRANSPORT=stdio.
- Performs boot reconciliation before serving.
"""
from __future__ import annotations
from mcp_devbench.mcp_server import mcp, boot_reconcile
from mcp_devbench.config import settings


def run() -> None:
    """Start the MCP server using configured transport.

    HTTP is the default transport for multi-client attach and streaming.
    STDIO fallback is provided for compatibility/testing.
    """
    # Ensure warm default exists before we accept requests.
    boot_reconcile()

    if settings.mcp_transport == "http":
        mcp.run_http(settings.mcp_http_host, settings.mcp_http_port)
    else:
        mcp.run_stdio()


if __name__ == "__main__":
    run()
