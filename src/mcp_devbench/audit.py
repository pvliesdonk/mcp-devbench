"""Structured audit logging to stdout.

Never log secrets; use small event names; JSON one-liners."""
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
    rec = {"audit": True, "event": event, **fields}
    log.info(json.dumps(rec))
