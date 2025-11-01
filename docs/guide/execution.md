# Command Execution

This guide covers executing commands in containers with MCP DevBench.

## Overview

MCP DevBench provides asynchronous command execution with:

- **Non-blocking execution** - Commands run in background
- **Streaming output** - Real-time stdout/stderr
- **Timeout handling** - Automatic termination
- **Signal support** - Send signals to running commands
- **Resource tracking** - CPU/memory usage stats
- **Concurrent execution** - Multiple commands per container

## Starting Execution

Start a command with `exec_start`:

```python
{
  "container_id": "c_abc123...",
  "cmd": ["python", "script.py"],
  "timeout_s": 300,
  "env": {"DEBUG": "true"},
  "workdir": "/workspace"
}
```

**Parameters:**

- `container_id` (required) - Container to execute in
- `cmd` (required) - Command and arguments as array
- `timeout_s` - Execution timeout in seconds (default: 300)
- `env` - Environment variables (optional)
- `workdir` - Working directory (default: `/workspace`)

**Returns:**

```python
{
  "exec_id": "e_xyz789...",
  "status": "running"
}
```

## Polling for Output

Poll for command output with `exec_poll`:

```python
{
  "exec_id": "e_xyz789...",
  "after_seq": 0
}
```

**Parameters:**

- `exec_id` (required) - Execution to poll
- `after_seq` - Return messages after this sequence number

**Returns:**

```python
{
  "messages": [
    {
      "seq": 1,
      "stream": "stdout",
      "data": "Hello, World!\n",
      "timestamp": "2024-01-15T10:30:01Z"
    },
    {
      "seq": 2,
      "stream": "stderr",
      "data": "Warning: deprecation\n",
      "timestamp": "2024-01-15T10:30:02Z"
    }
  ],
  "complete": false,
  "exit_code": null
}
```

When `complete` is `true`, the execution has finished and `exit_code` is set.

## Streaming Pattern

Typical polling loop:

```python
exec_id = exec_start(...)["exec_id"]
seq = 0

while True:
    result = exec_poll(exec_id, after_seq=seq)
    
    for msg in result["messages"]:
        print(f"{msg['stream']}: {msg['data']}")
        seq = msg["seq"]
    
    if result["complete"]:
        print(f"Exit code: {result['exit_code']}")
        break
    
    await asyncio.sleep(0.5)
```

## Sending Signals

Send signals to running executions with `exec_signal`:

```python
{
  "exec_id": "e_xyz789...",
  "signal": "SIGTERM"
}
```

**Supported signals:**

- `SIGTERM` - Graceful termination
- `SIGKILL` - Force kill
- `SIGINT` - Interrupt (Ctrl+C)
- `SIGHUP` - Hangup
- `SIGUSR1`, `SIGUSR2` - User-defined signals

## Execution Limits

### Timeout

Commands automatically timeout:

```bash
# Default timeout (seconds)
MCP_DEFAULT_EXEC_TIMEOUT=300

# Maximum allowed timeout
MCP_MAX_EXEC_TIMEOUT=3600
```

Timeout behavior:
1. Sends `SIGTERM` to process
2. Waits 10 seconds
3. Sends `SIGKILL` if still running

### Concurrency

Maximum concurrent executions per container:

```bash
MCP_MAX_CONCURRENT_EXECS=4
```

Exceeding this limit queues or rejects new executions.

## Resource Tracking

Poll result includes resource usage:

```python
{
  "complete": true,
  "exit_code": 0,
  "usage": {
    "cpu_time_ms": 1234,
    "memory_peak_mb": 45,
    "wall_time_ms": 5678
  }
}
```

## Examples

### Running Python Scripts

```python
# Write script
fs_write({
  "container_id": "c_abc...",
  "path": "/workspace/hello.py",
  "content": "print('Hello, World!')"
})

# Execute
exec_id = exec_start({
  "container_id": "c_abc...",
  "cmd": ["python", "/workspace/hello.py"],
  "timeout_s": 30
})["exec_id"]

# Poll for output
result = exec_poll({
  "exec_id": exec_id,
  "after_seq": 0
})
```

### Installing Packages

```python
exec_start({
  "container_id": "c_abc...",
  "cmd": ["pip", "install", "requests"],
  "timeout_s": 300
})
```

### Running Tests

```python
exec_start({
  "container_id": "c_abc...",
  "cmd": ["pytest", "/workspace/tests"],
  "timeout_s": 600,
  "env": {"PYTHONPATH": "/workspace"}
})
```

### Long-Running Processes

```python
# Start server
exec_id = exec_start({
  "container_id": "c_abc...",
  "cmd": ["python", "-m", "http.server", "8000"],
  "timeout_s": 3600
})["exec_id"]

# Later, stop it
exec_signal({
  "exec_id": exec_id,
  "signal": "SIGTERM"
})
```

## Best Practices

### Command Construction

✅ **Do:**
```python
cmd = ["python", "-c", "print('hello')"]
```

❌ **Don't:**
```python
cmd = ["python -c print('hello')"]  # Wrong! This is one string
```

### Error Handling

Always check exit codes:

```python
result = exec_poll(exec_id, after_seq=0)
if result["complete"]:
    if result["exit_code"] != 0:
        # Handle error
        print(f"Command failed with code {result['exit_code']}")
```

### Resource Usage

Monitor resource consumption:

```python
usage = result["usage"]
if usage["memory_peak_mb"] > 400:
    print("Warning: High memory usage")
```

### Timeouts

Set appropriate timeouts:

- Quick commands: 30-60 seconds
- Package installation: 300-600 seconds
- Tests: 600-1800 seconds
- Long-running: 3600+ seconds

## Troubleshooting

### Command Times Out

1. Check if command is CPU-bound
2. Increase timeout
3. Break into smaller steps
4. Check for deadlocks (waiting for input)

### High Memory Usage

1. Monitor with resource tracking
2. Reduce batch sizes
3. Use streaming processing
4. Increase container memory limit

### Command Not Starting

1. Verify container is running
2. Check concurrent execution limit
3. Review command syntax
4. Check file permissions

## Next Steps

- **[Filesystem Operations](filesystem.md)** - File management
- **[Container Management](containers.md)** - Container lifecycle
- **[Monitoring](monitoring.md)** - Performance tracking
