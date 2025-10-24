"""FastMCP2 server surface for M0.

- tool `ensure_default()` — idempotent warm default ensure + returns info.
- resource `default_container` — read-only info (ensures running).
"""
from fastmcp import FastMCP
from mcp_devbench.runtime_docker import ensure_default_container
from mcp_devbench.config import settings


mcp = FastMCP(settings.mcp_name)

@mcp.tool
def ensure_default() -> dict:
    return ensure_default_container()

@mcp.resource
def default_container() -> dict:
    return ensure_default_container()


def boot_reconcile() -> None:
    ensure_default_container()
