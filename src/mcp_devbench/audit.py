"""audit.py — structured audit logging to stdout.

Rules:
- Never log secret values; redact at source (we don't ingest secrets in M0).
- Use small, consistent event names (snake_case).
- Log JSON objects so ops can pipe to jq."""
from __future__ import annotations
import json
import logging
from mcp_devbench.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("mcp-devbench")


def audit(event: str, **fields) -> None:
    """Emit a single-line JSON audit event.

    Example:
        audit("container_created", id=cid, image=img)
    """
    rec = {"audit": True, "event": event, **fields}
    log.info(json.dumps(rec))
