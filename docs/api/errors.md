# Error Handling

Complete reference for error codes and handling in MCP DevBench.

## Error Format

```json
{
  "jsonrpc": "2.0",
  "id": "request-1",
  "error": {
    "code": -32000,
    "message": "Human-readable error message",
    "data": {
      "additional": "context"
    }
  }
}
```

## Error Codes

### JSON-RPC Errors

| Code | Name | Description |
|------|------|-------------|
| -32700 | Parse Error | Invalid JSON |
| -32600 | Invalid Request | Missing required fields |
| -32601 | Method Not Found | Unknown tool name |
| -32602 | Invalid Params | Invalid tool parameters |
| -32603 | Internal Error | Server error |

### Application Errors

| Code | Error | Description |
|------|-------|-------------|
| -32000 | Server Error | Generic server error |
| -32001 | Container Not Found | Container doesn't exist |
| -32002 | Image Not Allowed | Image not in allow-list |
| -32003 | Execution Timeout | Command timed out |
| -32004 | Path Security Error | Path outside workspace |
| -32005 | File Not Found | File doesn't exist |
| -32006 | Concurrent Limit Exceeded | Too many concurrent operations |
| -32007 | Authentication Required | Not authenticated |
| -32008 | Authorization Failed | Insufficient permissions |
| -32009 | Resource Exhausted | Out of resources |
| -32010 | Conflict | ETag mismatch or conflict |

## Error Handling Examples

### Python

```python
from mcp import Client, MCPError

try:
    result = await client.call_tool("spawn", {"image": "unknown:latest"})
except MCPError as e:
    if e.code == -32002:
        print(f"Image not allowed: {e.message}")
    elif e.code == -32001:
        print(f"Container not found: {e.message}")
    else:
        print(f"Unexpected error: {e}")
```

### JavaScript/TypeScript

```typescript
try {
  const result = await client.callTool('spawn', {
    image: 'unknown:latest'
  });
} catch (error) {
  if (error.code === -32002) {
    console.error('Image not allowed:', error.message);
  } else {
    console.error('Error:', error);
  }
}
```

## Retry Strategies

### Exponential Backoff

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(MCPError)
)
async def resilient_call():
    return await client.call_tool(...)
```

### Conditional Retry

```python
def should_retry(exception):
    # Retry only on specific errors
    return exception.code in [-32603, -32009]

@retry(
    stop=stop_after_attempt(3),
    retry=retry_if_exception(should_retry)
)
async def smart_retry():
    return await client.call_tool(...)
```

## Next Steps

- **[API Overview](overview.md)** - API documentation
- **[MCP Tools](tools.md)** - Tool reference
- **[Troubleshooting](../operations/troubleshooting.md)** - Debugging guide
