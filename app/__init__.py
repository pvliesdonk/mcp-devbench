"""
MCP Devbench

FastMCP2-based MCP server (M0):
- HTTP transport default (STDIO fallback).
- Boot reconciliation for a single warm default container.
- ENV-first config and SQLite durability.

Implementation lands across: config, errors, audit, state, runtime_docker, mcp_server, main.
"""
