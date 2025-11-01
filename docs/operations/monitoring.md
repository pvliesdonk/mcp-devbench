# Operations Monitoring

Monitoring and observability for production deployments.

## Metrics

MCP DevBench exports Prometheus metrics at `/metrics`.

### Key Metrics to Monitor

- `mcp_containers_total` - Total containers
- `mcp_containers_running` - Running containers
- `mcp_api_requests_total` - API requests
- `mcp_api_errors_total` - API errors
- `mcp_execution_duration_seconds` - Execution latency

### Grafana Dashboards

Import pre-built dashboards from GitHub repo.

## Logging

### Log Aggregation

Use Filebeat, Fluentd, or similar to ship logs to:
- Elasticsearch
- Loki
- CloudWatch
- Datadog

### Log Queries

Common queries:
- Failed authentications
- Container spawn failures
- Resource exhaustion
- Security violations

## Alerting

### Recommended Alerts

1. **High Error Rate** - Error rate > 5%
2. **Container Limit** - Too many containers
3. **High Latency** - P95 latency > 1s
4. **Failed Authentication** - Multiple auth failures
5. **Resource Usage** - High CPU/memory

See [Monitoring Guide](../guide/monitoring.md) for details.
