# Filesystem Operations

This guide covers file and directory operations in MCP DevBench.

## Overview

MCP DevBench provides secure filesystem operations:

- **Path validation** - All paths restricted to `/workspace`
- **Concurrent access** - ETag-based optimistic locking
- **Binary support** - Handle both text and binary files
- **Directory operations** - Create, list, delete directories
- **Atomic writes** - No partial file corruption

## Workspace Structure

All filesystem operations are constrained to `/workspace`:

```
/workspace/
├── your-files/
│   ├── script.py
│   └── data.json
├── output/
│   └── results.txt
└── temp/
```

Attempts to access paths outside `/workspace` are rejected.

## Reading Files

Read file contents with `fs_read`:

```python
{
  "container_id": "c_abc123...",
  "path": "/workspace/script.py"
}
```

**Returns:**

```python
{
  "content": "print('Hello, World!')",
  "size": 22,
  "etag": "abc123def456",
  "mtime": "2024-01-15T10:30:00Z"
}
```

### Binary Files

Binary files are base64-encoded:

```python
{
  "content": "iVBORw0KGgo...",  # base64-encoded
  "encoding": "base64",
  "size": 1234
}
```

## Writing Files

Write file contents with `fs_write`:

```python
{
  "container_id": "c_abc123...",
  "path": "/workspace/hello.py",
  "content": "print('Hello, World!')",
  "mode": 0o644,
  "create_parents": true
}
```

**Parameters:**

- `container_id` (required) - Container ID
- `path` (required) - File path
- `content` (required) - File contents (string or base64)
- `mode` - File permissions (default: 0o644)
- `create_parents` - Create parent directories (default: true)
- `if_match` - ETag for optimistic locking (optional)

**Returns:**

```python
{
  "size": 22,
  "etag": "new123abc456"
}
```

### Concurrent Writes

Use ETags to prevent conflicts:

```python
# Read file
result = fs_read({
  "container_id": "c_abc...",
  "path": "/workspace/data.json"
})

# Modify content
content = modify(result["content"])

# Write with ETag check
fs_write({
  "container_id": "c_abc...",
  "path": "/workspace/data.json",
  "content": content,
  "if_match": result["etag"]
})
```

If another client modified the file, write fails with conflict error.

## Listing Directories

List directory contents with `fs_list`:

```python
{
  "container_id": "c_abc123...",
  "path": "/workspace",
  "recursive": false
}
```

**Returns:**

```python
{
  "entries": [
    {
      "path": "/workspace/script.py",
      "type": "file",
      "size": 1234,
      "mtime": "2024-01-15T10:30:00Z",
      "mode": 0o644
    },
    {
      "path": "/workspace/output",
      "type": "directory",
      "mtime": "2024-01-15T10:30:00Z",
      "mode": 0o755
    }
  ]
}
```

### Recursive Listing

List all files recursively:

```python
{
  "container_id": "c_abc...",
  "path": "/workspace",
  "recursive": true
}
```

## Deleting Files

Delete files or directories with `fs_delete`:

```python
{
  "container_id": "c_abc123...",
  "path": "/workspace/temp/file.txt",
  "recursive": false
}
```

**Parameters:**

- `container_id` (required) - Container ID
- `path` (required) - File or directory path
- `recursive` - Delete directory and contents (default: false)

**Returns:**

```python
{
  "status": "deleted",
  "path": "/workspace/temp/file.txt"
}
```

!!! warning
    Recursive deletion is permanent and cannot be undone!

## File Permissions

### Default Permissions

- Files: 0o644 (rw-r--r--)
- Directories: 0o755 (rwxr-xr-x)

### Custom Permissions

Set custom permissions:

```python
fs_write({
  "container_id": "c_abc...",
  "path": "/workspace/script.sh",
  "content": "#!/bin/bash\necho 'hello'",
  "mode": 0o755  # Executable
})
```

## Path Security

### Validation

All paths are validated:

✅ **Allowed:**
```
/workspace/file.txt
/workspace/subdir/file.txt
./file.txt  (relative to /workspace)
```

❌ **Rejected:**
```
/etc/passwd
../../../etc/passwd
/workspace/../etc/passwd
```

### Symlink Protection

Symlinks outside `/workspace` are rejected:

```python
# This will fail if symlink points outside workspace
fs_read({
  "container_id": "c_abc...",
  "path": "/workspace/link-to-etc"
})
```

## File Size Limits

Maximum file size is configurable:

```bash
MCP_MAX_FILE_SIZE=100  # MB
```

Exceeding this limit returns an error.

## Examples

### Creating Directory Structure

```python
# Create nested directories
fs_write({
  "container_id": "c_abc...",
  "path": "/workspace/project/src/main.py",
  "content": "def main(): pass",
  "create_parents": true
})
```

### Copying Files

```python
# Read source
result = fs_read({
  "container_id": "c_abc...",
  "path": "/workspace/source.txt"
})

# Write to destination
fs_write({
  "container_id": "c_abc...",
  "path": "/workspace/backup/source.txt",
  "content": result["content"],
  "create_parents": true
})
```

### Processing Files

```python
# Read file
result = fs_read({
  "container_id": "c_abc...",
  "path": "/workspace/data.json"
})

# Process content (in your code)
data = json.loads(result["content"])
data["processed"] = True
new_content = json.dumps(data, indent=2)

# Write back
fs_write({
  "container_id": "c_abc...",
  "path": "/workspace/data.json",
  "content": new_content,
  "if_match": result["etag"]
})
```

### Cleaning Up

```python
# Delete temporary files
fs_delete({
  "container_id": "c_abc...",
  "path": "/workspace/temp",
  "recursive": true
})
```

## Best Practices

### ETags

Always use ETags for files that multiple clients might modify:

```python
# ✅ Good
result = fs_read(...)
fs_write(..., if_match=result["etag"])

# ❌ Bad (race condition)
result = fs_read(...)
# ... time passes ...
fs_write(...)  # No ETag check!
```

### File Organization

Organize files in subdirectories:

```
/workspace/
├── src/          # Source code
├── data/         # Input data
├── output/       # Results
└── temp/         # Temporary files
```

### Cleanup

Delete temporary files when done:

```python
try:
    # Work with temporary files
    ...
finally:
    # Cleanup
    fs_delete({
      "container_id": c_id,
      "path": "/workspace/temp",
      "recursive": true
    })
```

### Large Files

For large files:
1. Stream through command execution instead
2. Break into chunks
3. Use compression
4. Increase file size limit

## Troubleshooting

### Path Security Error

If you get "path outside workspace" error:

1. Check path starts with `/workspace`
2. Verify no `..` components
3. Ensure symlinks stay in workspace

### ETag Conflict

If write fails with conflict:

1. Re-read file to get new ETag
2. Merge changes if needed
3. Retry write with new ETag

### Permission Denied

If operation fails with permission error:

1. Check container is running as correct user
2. Verify file permissions
3. Check parent directory permissions

## Next Steps

- **[Command Execution](execution.md)** - Run commands
- **[Container Management](containers.md)** - Container lifecycle
- **[Security](security.md)** - Security model
