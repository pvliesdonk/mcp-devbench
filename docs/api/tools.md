# MCP Tools Reference

Complete reference for all MCP tools available in MCP DevBench.

## Container Management Tools

### spawn

Create a new Docker container.

**Input:**
```json
{
  "image": "python:3.11-slim",
  "persistent": false,
  "alias": "my-workspace",
  "ttl_s": 3600,
  "idempotency_key": "optional-key"
}
```

**Output:**
```json
{
  "container_id": "c_abc123...",
  "alias": "my-workspace",
  "status": "running"
}
```

**Parameters:**
- `image` (required) - Docker image reference
- `persistent` (optional) - Whether container persists across restarts (default: false)
- `alias` (optional) - User-friendly name for the container
- `ttl_s` (optional) - Time-to-live in seconds
- `idempotency_key` (optional) - Key to prevent duplicate creation

---

### attach

Attach client session to a container.

**Input:**
```json
{
  "target": "my-workspace",
  "client_name": "claude",
  "session_id": "unique-session-id"
}
```

**Output:**
```json
{
  "container_id": "c_abc123...",
  "alias": "my-workspace",
  "roots": ["workspace:c_abc123..."]
}
```

---

### kill

Stop and remove a container.

**Input:**
```json
{
  "container_id": "c_abc123...",
  "force": true
}
```

**Output:**
```json
{
  "status": "stopped"
}
```

---

### list

List all containers.

**Input:**
```json
{
  "include_stopped": false
}
```

**Output:**
```json
{
  "containers": [
    {
      "container_id": "c_abc123...",
      "alias": "my-workspace",
      "image": "python:3.11-slim",
      "status": "running",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

## Execution Tools

### exec_start

Start command execution in a container.

**Input:**
```json
{
  "container_id": "c_abc123...",
  "cmd": ["python", "script.py"],
  "cwd": "/workspace",
  "env": {"DEBUG": "true"},
  "timeout_s": 300
}
```

**Output:**
```json
{
  "exec_id": "e_xyz789...",
  "status": "running"
}
```

---

### exec_poll

Poll for command execution output.

**Input:**
```json
{
  "exec_id": "e_xyz789...",
  "after_seq": 0
}
```

**Output:**
```json
{
  "messages": [
    {
      "seq": 1,
      "stream": "stdout",
      "data": "Hello, World!\n",
      "timestamp": "2024-01-15T10:30:01Z"
    }
  ],
  "complete": false,
  "exit_code": null
}
```

---

### exec_signal

Send signal to running execution.

**Input:**
```json
{
  "exec_id": "e_xyz789...",
  "signal": "SIGTERM"
}
```

**Output:**
```json
{
  "status": "signaled"
}
```

## Filesystem Tools

### fs_read

Read file contents from container.

**Input:**
```json
{
  "container_id": "c_abc123...",
  "path": "/workspace/file.txt"
}
```

**Output:**
```json
{
  "content": "file contents",
  "size": 13,
  "etag": "abc123def456",
  "mtime": "2024-01-15T10:30:00Z"
}
```

---

### fs_write

Write file contents to container.

**Input:**
```json
{
  "container_id": "c_abc123...",
  "path": "/workspace/file.txt",
  "content": "new contents",
  "mode": 420,
  "create_parents": true,
  "if_match": "abc123def456"
}
```

**Output:**
```json
{
  "size": 12,
  "etag": "new123abc456"
}
```

---

### fs_delete

Delete file or directory from container.

**Input:**
```json
{
  "container_id": "c_abc123...",
  "path": "/workspace/temp",
  "recursive": true
}
```

**Output:**
```json
{
  "status": "deleted",
  "path": "/workspace/temp"
}
```

---

### fs_list

List directory contents in container.

**Input:**
```json
{
  "container_id": "c_abc123...",
  "path": "/workspace",
  "recursive": false
}
```

**Output:**
```json
{
  "entries": [
    {
      "path": "/workspace/file.txt",
      "type": "file",
      "size": 1234,
      "mtime": "2024-01-15T10:30:00Z",
      "mode": 420
    }
  ]
}
```

## Error Responses

All tools may return errors in this format:

```json
{
  "error": {
    "code": -32000,
    "message": "Error description",
    "data": {
      "details": "Additional error information"
    }
  }
}
```

See [Error Handling](errors.md) for complete error code reference.

## Next Steps

- **[API Overview](overview.md)** - API architecture
- **[Authentication](authentication.md)** - Authentication methods
- **[Error Handling](errors.md)** - Error codes
