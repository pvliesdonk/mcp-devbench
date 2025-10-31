"""Prometheus metrics collection for MCP DevBench."""

from typing import Optional

from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


class MetricsCollector:
    """Collects and exposes Prometheus metrics for MCP DevBench operations."""

    def __init__(self):
        """Initialize metrics collector with all metrics."""
        # Counter metrics
        self.container_spawns_total = Counter(
            "mcp_devbench_container_spawns_total",
            "Total number of container spawns",
            ["image"],
        )

        self.exec_total = Counter(
            "mcp_devbench_exec_total",
            "Total number of command executions",
            ["container_id", "status"],
        )

        self.fs_operations_total = Counter(
            "mcp_devbench_fs_operations_total",
            "Total number of filesystem operations",
            ["op_type"],
        )

        # Histogram metrics
        self.exec_duration_seconds = Histogram(
            "mcp_devbench_exec_duration_seconds",
            "Execution duration in seconds",
            buckets=[0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0],
        )

        self.output_bytes = Histogram(
            "mcp_devbench_output_bytes",
            "Output size in bytes",
            buckets=[100, 1000, 10000, 100000, 1000000, 10000000],
        )

        # Gauge metrics
        self.active_containers = Gauge(
            "mcp_devbench_active_containers",
            "Number of active containers",
        )

        self.active_attachments = Gauge(
            "mcp_devbench_active_attachments",
            "Number of active client attachments",
        )

        self.memory_usage_bytes = Gauge(
            "mcp_devbench_memory_usage_bytes",
            "Memory usage in bytes per container",
            ["container_id"],
        )

    def record_container_spawn(self, image: str) -> None:
        """
        Record a container spawn.

        Args:
            image: Image used for the container
        """
        self.container_spawns_total.labels(image=image).inc()

    def record_exec(self, container_id: str, status: str) -> None:
        """
        Record a command execution.

        Args:
            container_id: Container ID where the command was executed
            status: Execution status (success, failure, cancelled)
        """
        self.exec_total.labels(container_id=container_id, status=status).inc()

    def record_exec_duration(self, duration_seconds: float) -> None:
        """
        Record execution duration.

        Args:
            duration_seconds: Duration in seconds
        """
        self.exec_duration_seconds.observe(duration_seconds)

    def record_fs_operation(self, op_type: str) -> None:
        """
        Record a filesystem operation.

        Args:
            op_type: Type of operation (read, write, delete, stat, list)
        """
        self.fs_operations_total.labels(op_type=op_type).inc()

    def record_output_size(self, size_bytes: int) -> None:
        """
        Record output size.

        Args:
            size_bytes: Size in bytes
        """
        self.output_bytes.observe(size_bytes)

    def set_active_containers(self, count: int) -> None:
        """
        Set the number of active containers.

        Args:
            count: Number of active containers
        """
        self.active_containers.set(count)

    def set_active_attachments(self, count: int) -> None:
        """
        Set the number of active attachments.

        Args:
            count: Number of active attachments
        """
        self.active_attachments.set(count)

    def set_container_memory(self, container_id: str, memory_bytes: int) -> None:
        """
        Set memory usage for a container.

        Args:
            container_id: Container ID
            memory_bytes: Memory usage in bytes
        """
        self.memory_usage_bytes.labels(container_id=container_id).set(memory_bytes)

    def get_metrics(self) -> bytes:
        """
        Get current metrics in Prometheus format.

        Returns:
            Metrics data in bytes
        """
        return generate_latest()


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get the global metrics collector instance.

    Returns:
        MetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
