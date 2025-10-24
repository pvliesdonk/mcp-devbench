"""errors.py — fixed error taxonomy mapping for MCP Devbench.

The taxonomy aligns with the architecture doc:
InvalidArgument, NotAllowed, NotFound, Conflict, ResourceExhausted, DeadlineExceeded,
Internal, Unavailable, Cancelled.

In M0 we mainly surface Unavailable (Docker issues) and Internal (unexpected)."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class TaxonomyError(Exception):
    """Error carrying a stable taxonomy code, HTTP-style status, and optional detail.

    Attributes:
        code: One of the fixed taxonomy keys.
        message: Human-friendly error message.
        status_code: Numeric status (diagnostic; not an HTTP response here).
        detail: Optional structured metadata (safe to log).
    """
    code: str
    message: str
    status_code: int = 500
    detail: dict | None = None

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code}: {self.message}"


def as_taxonomy(exc: Exception) -> TaxonomyError:
    """Wrap any exception as a TaxonomyError with sensible defaults.

    - Pass-through if already a TaxonomyError.
    - Unknown exceptions map to Internal.
    """
    if isinstance(exc, TaxonomyError):
        return exc
    return TaxonomyError("Internal", str(exc) or "internal error", 500)
