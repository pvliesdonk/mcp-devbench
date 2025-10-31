# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-10-31

### Added
- **Epic 1: Foundation Layer**
  - Project scaffold with FastMCP 2 integration
  - ENV-based configuration with Pydantic Settings
  - SQLite state management with SQLAlchemy and Alembic
  - Docker container lifecycle manager with label-based tracking
  - Health check endpoint

- **Epic 2: Command Execution Engine**
  - Async exec core with docker-py integration
  - Parallel execution with semaphore-based limiting (4 concurrent per container)
  - Output streaming with bounded ring buffers (64MB default)
  - Cursor-based polling mechanism for ordered delivery
  - Exec cancellation support with SIGTERM/SIGKILL
  - Idempotency keys with 24-hour TTL
  - Resource tracking (CPU, memory, wall time)

- **Epic 3: Filesystem Operations**
  - Complete filesystem manager for workspace operations
  - Read, write, delete, stat, and list operations
  - Path security validation (prevents escape from /workspace)
  - ETag implementation for concurrency control
  - Binary and text file support
  - Batch filesystem operations with transaction support
  - Tar-based import/export with streaming support

- **Epic 4: MCP Protocol Integration**
  - 9 MCP tool endpoints with typed Pydantic models:
    - `spawn` - Container creation with persistence/alias support
    - `attach` - Client session tracking with workspace roots
    - `kill` - Container removal with attachment cleanup
    - `exec_start` - Command execution with idempotency keys
    - `exec_cancel` - Execution cancellation
    - `exec_poll` - Cursor-based output streaming
    - `fs_read` - Read files with metadata and ETags
    - `fs_write` - Write files with ETag-based concurrency control
    - `fs_delete` - Delete files and directories
    - `fs_stat` - Get file/directory metadata
    - `fs_list` - List directory contents
  - Comprehensive error handling with proper exception types
  - Access control validation
  - Type-safe API with FileStatOutput for directory listings

- **Infrastructure & Tooling**
  - Multi-stage Dockerfile using official UV image for fast builds
  - GitHub Actions CI/CD workflow with automated testing
  - Test coverage reporting with pytest-cov (79.68% coverage)
  - Automated release workflow with PyPI publishing
  - Comprehensive documentation with API reference and examples

### Fixed
- fs_read now properly unpacks tuple from manager.read() (performance optimization)
- Moved local imports to top of file per PEP 8 conventions
- Removed unused mock from test_exec_poll_tool
- Fixed test patching for get_output_streamer

### Changed
- FileListOutput.entries now uses List[FileStatOutput] for better type safety
- All 90 tests passing (100% success rate)
- Zero linting issues with ruff

[0.1.0]: https://github.com/pvliesdonk/mcp-devbench/releases/tag/v0.1.0
