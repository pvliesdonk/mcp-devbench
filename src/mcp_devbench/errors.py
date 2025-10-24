"""Fixed error taxonomy mapping for MCP Devbench.

Taxonomy: InvalidArgument, NotAllowed, NotFound, Conflict, ResourceExhausted,
DeadlineExceeded, Internal, Unavailable, Cancelled."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(slots=True)
class TaxonomyError(Exception):
    code: str
    message: str
    status_code: int = 500
    detail: dict | None = None

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.code}: {self.message}"


def as_taxonomy(exc: Exception) -> TaxonomyError:
    if isinstance(exc, TaxonomyError):
        return exc
    return TaxonomyError("Internal", str(exc) or "internal error", 500)
