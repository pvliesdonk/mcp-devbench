# Monitoring

This guide covers monitoring and observability in MCP DevBench.

## Overview

MCP DevBench provides comprehensive observability:

- **Prometheus Metrics** - Time-series metrics
- **Structured Logging** - JSON-formatted logs
- **Health Checks** - Ready and live endpoints
- **Audit Logs** - Operation history
- **Performance Tracking** - Resource usage

## Prometheus Metrics

### Enabling Metrics

Enable Prometheus metrics:

```bash
MCP_METRICS_ENABLED=true
MCP_METRICS_PORT=9090
```

Metrics are exposed at `http://localhost:9090/metrics`.

### Available Metrics

**Container Metrics:**

- `mcp_containers_total` - Total number of containers
- `mcp_containers_running` - Running containers
- `mcp_containers_stopped` - Stopped containers
- `mcp_container_spawns_total` - Total container spawns
- `mcp_container_spawn_duration_seconds` - Spawn duration histogram

**Execution Metrics:**

- `mcp_executions_total` - Total command executions
- `mcp_executions_running` - Running executions
- `mcp_execution_duration_seconds` - Execution duration histogram
- `mcp_execution_timeout_total` - Total timeouts

**Filesystem Metrics:**

- `mcp_fs_operations_total` - Total filesystem operations
- `mcp_fs_read_bytes_total` - Total bytes read
- `mcp_fs_write_bytes_total` - Total bytes written
- `mcp_fs_operation_duration_seconds` - Operation duration histogram

**System Metrics:**

- `mcp_server_uptime_seconds` - Server uptime
- `mcp_api_requests_total` - Total API requests
- `mcp_api_request_duration_seconds` - Request duration histogram
- `mcp_api_errors_total` - Total API errors

### Example Queries

**Container spawn rate:**
```promql
rate(mcp_container_spawns_total[5m])
```

**Average execution time:**
```promql
histogram_quantile(0.95, mcp_execution_duration_seconds)
```

**Error rate:**
```promql
rate(mcp_api_errors_total[5m])
```

**Resource usage:**
```promql
sum(container_memory_usage_bytes{container=~"mcp-devbench.*"})
```

## Structured Logging

### Log Configuration

Configure logging:

```bash
# Log level
MCP_LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Log format
MCP_LOG_FORMAT=json  # json or text
```

### Log Format

JSON-structured logs:

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "logger": "mcp_devbench.managers.container_manager",
  "message": "Container created",
  "container_id": "c_abc123",
  "image": "python:3.11-slim",
  "client_name": "claude",
  "session_id": "session-123",
  "correlation_id": "req-xyz789"
}
```

### Log Levels

- **DEBUG** - Detailed debugging information
- **INFO** - General informational messages
- **WARNING** - Warning messages (non-critical issues)
- **ERROR** - Error messages (operations failed)
- **CRITICAL** - Critical issues (server cannot continue)

### Correlation IDs

Each request gets a unique correlation ID for tracing through logs:

```json
{
  "correlation_id": "req-abc123",
  "message": "Starting container spawn"
}
```

## Health Checks

### Endpoints

**Readiness:**
```bash
curl http://localhost:8000/health/ready
```

Returns 200 if server is ready to accept requests.

**Liveness:**
```bash
curl http://localhost:8000/health/live
```

Returns 200 if server is running.

### Kubernetes

Health check configuration for Kubernetes:

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
```

## Audit Logging

### Configuration

Enable audit logging:

```bash
MCP_AUDIT_ENABLED=true
MCP_AUDIT_LOG_FILE=/var/log/mcp-devbench/audit.log
```

### Audit Events

Events logged:

- `container.spawn` - Container created
- `container.attach` - Client attached
- `container.kill` - Container stopped
- `exec.start` - Command started
- `exec.signal` - Signal sent
- `fs.read` - File read
- `fs.write` - File written
- `fs.delete` - File deleted

### Audit Format

```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "event_type": "container.spawn",
  "client_name": "claude",
  "session_id": "session-123",
  "container_id": "c_abc123",
  "image": "python:3.11-slim",
  "result": "success",
  "duration_ms": 1234
}
```

## Dashboards

### Grafana Dashboard

Example Grafana dashboard panels:

**Container Count:**
```promql
mcp_containers_running
```

**Request Rate:**
```promql
sum(rate(mcp_api_requests_total[5m])) by (method)
```

**Error Rate:**
```promql
sum(rate(mcp_api_errors_total[5m])) by (error_type)
```

**P95 Latency:**
```promql
histogram_quantile(0.95, rate(mcp_api_request_duration_seconds_bucket[5m]))
```

### Example Dashboard

```json
{
  "dashboard": {
    "title": "MCP DevBench",
    "panels": [
      {
        "title": "Container Count",
        "targets": [
          {
            "expr": "mcp_containers_running"
          }
        ]
      },
      {
        "title": "Request Rate",
        "targets": [
          {
            "expr": "rate(mcp_api_requests_total[5m])"
          }
        ]
      }
    ]
  }
}
```

## Alerting

### Alert Rules

Example Prometheus alert rules:

**High Error Rate:**
```yaml
- alert: HighErrorRate
  expr: rate(mcp_api_errors_total[5m]) > 0.05
  for: 5m
  annotations:
    summary: "High error rate detected"
```

**Container Limit:**
```yaml
- alert: TooManyContainers
  expr: mcp_containers_total > 100
  for: 5m
  annotations:
    summary: "Too many containers running"
```

**High Memory:**
```yaml
- alert: HighMemoryUsage
  expr: container_memory_usage_bytes > 1e9
  for: 5m
  annotations:
    summary: "High memory usage"
```

### Notification Channels

Configure alerts to send to:
- Email
- Slack
- PagerDuty
- OpsGenie
- Webhook

## Performance Monitoring

### Key Metrics

Monitor these metrics:

1. **Latency** - P50, P95, P99 request times
2. **Throughput** - Requests per second
3. **Error Rate** - Failed requests percentage
4. **Saturation** - Resource utilization

### SLIs/SLOs

Example Service Level Indicators:

- **Availability:** 99.9% uptime
- **Latency:** P95 < 100ms
- **Error Rate:** < 0.1%
- **Container Spawn Time:** P95 < 5s

## Tracing (Planned)

Future distributed tracing with OpenTelemetry:

```bash
MCP_TRACING_ENABLED=true
MCP_TRACING_ENDPOINT=http://jaeger:14268/api/traces
```

Will provide:
- Request tracing across components
- Dependency mapping
- Performance bottleneck identification

## Log Aggregation

### ELK Stack

Ship logs to Elasticsearch:

```bash
# Filebeat configuration
filebeat.inputs:
- type: log
  paths:
    - /var/log/mcp-devbench/*.log
  json.keys_under_root: true

output.elasticsearch:
  hosts: ["elasticsearch:9200"]
```

### Loki

Ship logs to Grafana Loki:

```yaml
# Promtail configuration
clients:
  - url: http://loki:3100/loki/api/v1/push

scrape_configs:
  - job_name: mcp-devbench
    static_configs:
      - targets:
          - localhost
        labels:
          app: mcp-devbench
          __path__: /var/log/mcp-devbench/*.log
```

## Best Practices

### Metrics

1. **Use histograms** for latency tracking
2. **Track percentiles** (P50, P95, P99)
3. **Monitor trends** over time
4. **Set up alerts** for anomalies
5. **Export to long-term storage**

### Logging

1. **Use structured logging** (JSON)
2. **Include correlation IDs**
3. **Log at appropriate levels**
4. **Don't log sensitive data**
5. **Rotate logs regularly**

### Alerting

1. **Avoid alert fatigue** (tune thresholds)
2. **Use actionable alerts** only
3. **Include context** in notifications
4. **Define escalation policies**
5. **Test alerts regularly**

## Troubleshooting

### High Memory Usage

Check metrics:
```promql
container_memory_usage_bytes{container=~"mcp-devbench.*"}
```

### Slow Requests

Check latency histogram:
```promql
histogram_quantile(0.95, mcp_api_request_duration_seconds_bucket)
```

### Container Leaks

Check container count trend:
```promql
mcp_containers_total
```

## Next Steps

- **[Operations](../operations/deployment.md)** - Deploy with monitoring
- **[Troubleshooting](../operations/troubleshooting.md)** - Debug issues
- **[Security](security.md)** - Monitor security
