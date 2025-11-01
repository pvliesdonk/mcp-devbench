# Architecture

MCP DevBench architecture overview.

## System Architecture

```
┌──────────────┐
│  MCP Client  │
└──────┬───────┘
       │ MCP Protocol
┌──────▼────────────┐
│  FastMCP Server   │
│  (Auth, Routing)  │
└──────┬────────────┘
       │
    ┌──┴──┬──────┬────────┐
    │     │      │        │
┌───▼──┐ ┌▼─┐ ┌─▼──┐ ┌──▼───┐
│ Cont │ │Ex│ │ FS │ │ Img  │
│ Mgr  │ │ec│ │Mgr │ │Policy│
└───┬──┘ └┬─┘ └─┬──┘ └──┬───┘
    │     │     │       │
    └─────┴─────┴───────┘
            │
    ┌───────▼───────┐
    │ Docker Daemon │
    └───────────────┘
```

## Components

### Managers

- **ContainerManager** - Container lifecycle
- **ExecManager** - Command execution
- **FilesystemManager** - File operations
- **ImagePolicyManager** - Image validation
- **SecurityManager** - Security policies

### Repositories

- **ContainerRepository** - Container data access
- **ExecRepository** - Execution data access
- **AttachmentRepository** - Attachment data access

### Utilities

- **AuditLogger** - Audit trail
- **MetricsCollector** - Prometheus metrics
- **DockerClient** - Docker API wrapper

## Design Patterns

- **Repository Pattern** - Data access abstraction
- **Manager Pattern** - Business logic
- **Dependency Injection** - Loose coupling
- **Factory Pattern** - Object creation

## Next Steps

- [Project Style](project-style.md)
- [Testing](testing.md)
