"""mcp_server.py — FastMCP2 server surface for M0.

Exposes:
- tool `ensure_default()` — idempotent warm default ensure + returns info.
- resource `default_container` — read-only info (ensures running).

Boot reconciliation is performed before serving (in main), but tools
are also idempotent, so clients can call them anytime."""
from fastmcp import FastMCP
from mcp_devbench.runtime_docker import ensure_default_container
from mcp_devbench.config import settings


mcp = FastMCP(settings.mcp_name)

@mcp.tool
def ensure_default() -> dict:
    """Ensure the warm default container is running; return its info.

    Returns:
        dict: { id, alias, image, state }
    """
    return ensure_default_container()

@mcp.resource
def default_container() -> dict:
    """Read-only default container info (ensures running).
    """
    return ensure_default_container()


def boot_reconcile() -> None:
    """Run reconciliation once.
    """
    ensure_default_container()
