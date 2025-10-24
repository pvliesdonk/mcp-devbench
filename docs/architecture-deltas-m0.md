# Architecture deltas for M0

- Removed Ops sidecar (no `/healthz`, `/metrics`).
- Standardized on **FastMCP2 HTTP** as default transport; STDIO as fallback.
- Acceptance change: replace SSE demo with HTTP streaming verified via FastMCP2 (to be proven in later PR alongside exec engine).
