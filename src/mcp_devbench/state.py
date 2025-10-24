"""state.py — lightweight SQLite durability layer.

Tables (M0):
- containers(id TEXT PK, alias TEXT UNIQUE, image TEXT, is_default INT, created_at TEXT).

Concurrency: single connection, short transactions (safe for M0 load)."""
from __future__ import annotations
import sqlite3
from mcp_devbench.config import settings
from mcp_devbench.audit import audit

# Open a single connection; WAL mode for durability and concurrent readers.
conn = sqlite3.connect(settings.sqlite_path, check_same_thread=False)
conn.executescript(
    """
CREATE TABLE IF NOT EXISTS containers (
  id TEXT PRIMARY KEY,
  alias TEXT UNIQUE,
  image TEXT NOT NULL,
  is_default INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

"""
)
conn.commit()
audit("sqlite_initialized", path=settings.sqlite_path)


def upsert_container(container_id: str, alias: str, image: str, is_default: int = 1) -> None:
    """Insert or update a container row.

    Args:
        container_id: Opaque Docker container id.
        alias: Logical alias (`default` in M0).
        image: Image name (e.g., ubuntu:24.04).
        is_default: 1 for default container.
    """
    conn.execute(
        (
            "INSERT INTO containers (id, alias, image, is_default) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET alias=excluded.alias, image=excluded.image, is_default=excluded.is_default"
        ),
        (container_id, alias, image, is_default),
    )
    conn.commit()


def find_by_alias(alias: str) -> dict | None:
    """Return a container row by alias or None.

    Returns keys: id, alias, image, is_default.
    """
    cur = conn.execute("SELECT id, alias, image, is_default FROM containers WHERE alias = ?", (alias,))
    row = cur.fetchone()
    return dict(zip([c[0] for c in cur.description], row)) if row else None
