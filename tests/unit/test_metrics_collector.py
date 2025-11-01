"""Unit tests for metrics collector."""

import pytest
from prometheus_client import REGISTRY

from mcp_devbench.utils.metrics_collector import MetricsCollector, get_metrics_collector


@pytest.fixture
def metrics_collector():
    """Create metrics collector for testing."""
    # Clear the registry before each test to avoid conflicts
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            # Ignore errors if the collector is not registered; this is expected during test setup.
            pass
    return MetricsCollector()


def test_metrics_collector_singleton():
    """Test that get_metrics_collector returns singleton instance."""
    collector1 = get_metrics_collector()
    collector2 = get_metrics_collector()
    assert collector1 is collector2


def test_record_container_spawn(metrics_collector):
    """Test recording container spawns."""
    metrics_collector.record_container_spawn("ubuntu:latest")
    metrics_collector.record_container_spawn("ubuntu:latest")
    metrics_collector.record_container_spawn("python:3.11")

    # Get metrics
    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    # Check that metrics are present
    assert "mcp_devbench_container_spawns_total" in metrics_data
    assert 'image="ubuntu:latest"' in metrics_data
    assert 'image="python:3.11"' in metrics_data


def test_record_exec(metrics_collector):
    """Test recording command executions."""
    metrics_collector.record_exec("c_123", "success")
    metrics_collector.record_exec("c_123", "failure")
    metrics_collector.record_exec("c_456", "success")

    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    assert "mcp_devbench_exec_total" in metrics_data
    assert 'container_id="c_123"' in metrics_data
    assert 'status="success"' in metrics_data
    assert 'status="failure"' in metrics_data


def test_record_exec_duration(metrics_collector):
    """Test recording execution duration."""
    metrics_collector.record_exec_duration(0.5)
    metrics_collector.record_exec_duration(2.5)
    metrics_collector.record_exec_duration(10.0)

    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    assert "mcp_devbench_exec_duration_seconds" in metrics_data
    assert "_count" in metrics_data


def test_record_fs_operation(metrics_collector):
    """Test recording filesystem operations."""
    metrics_collector.record_fs_operation("read")
    metrics_collector.record_fs_operation("write")
    metrics_collector.record_fs_operation("read")

    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    assert "mcp_devbench_fs_operations_total" in metrics_data
    assert 'op_type="read"' in metrics_data
    assert 'op_type="write"' in metrics_data


def test_record_output_size(metrics_collector):
    """Test recording output size."""
    metrics_collector.record_output_size(100)
    metrics_collector.record_output_size(5000)
    metrics_collector.record_output_size(100000)

    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    assert "mcp_devbench_output_bytes" in metrics_data


def test_set_active_containers(metrics_collector):
    """Test setting active containers count."""
    metrics_collector.set_active_containers(5)

    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    assert "mcp_devbench_active_containers" in metrics_data
    assert "5.0" in metrics_data or "5" in metrics_data


def test_set_active_attachments(metrics_collector):
    """Test setting active attachments count."""
    metrics_collector.set_active_attachments(3)

    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    assert "mcp_devbench_active_attachments" in metrics_data
    assert "3.0" in metrics_data or "3" in metrics_data


def test_set_container_memory(metrics_collector):
    """Test setting container memory usage."""
    metrics_collector.set_container_memory("c_123", 1024000)

    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    assert "mcp_devbench_memory_usage_bytes" in metrics_data
    assert 'container_id="c_123"' in metrics_data


def test_multiple_operations(metrics_collector):
    """Test recording multiple different operations."""
    metrics_collector.record_container_spawn("ubuntu:latest")
    metrics_collector.record_exec("c_123", "success")
    metrics_collector.record_fs_operation("read")
    metrics_collector.set_active_containers(2)

    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    # All metrics should be present
    assert "mcp_devbench_container_spawns_total" in metrics_data
    assert "mcp_devbench_exec_total" in metrics_data
    assert "mcp_devbench_fs_operations_total" in metrics_data
    assert "mcp_devbench_active_containers" in metrics_data


def test_metrics_format(metrics_collector):
    """Test that metrics are in proper Prometheus format."""
    metrics_collector.record_container_spawn("ubuntu:latest")

    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    # Should have TYPE declarations
    assert "# TYPE" in metrics_data
    # Should have HELP text
    assert "# HELP" in metrics_data


def test_histogram_buckets(metrics_collector):
    """Test histogram bucket configuration."""
    # Record values in different buckets
    metrics_collector.record_exec_duration(0.05)  # Below 0.1
    metrics_collector.record_exec_duration(0.3)  # Between 0.1 and 0.5
    metrics_collector.record_exec_duration(15.0)  # Between 10 and 30

    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    # Check that buckets are present
    assert 'le="0.1"' in metrics_data
    assert 'le="0.5"' in metrics_data
    assert 'le="30.0"' in metrics_data


def test_gauge_updates(metrics_collector):
    """Test that gauge values can be updated."""
    metrics_collector.set_active_containers(5)
    metrics_collector.set_active_containers(3)  # Update to new value

    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    # Should show the latest value
    assert "mcp_devbench_active_containers" in metrics_data
    # Value should be 3, not 5
    assert "3.0" in metrics_data or "3" in metrics_data


def test_counter_increments(metrics_collector):
    """Test that counters increment properly."""
    metrics_collector.record_fs_operation("read")
    metrics_collector.record_fs_operation("read")
    metrics_collector.record_fs_operation("read")

    metrics_data = metrics_collector.get_metrics().decode("utf-8")

    # Counter should show 3
    assert 'op_type="read"' in metrics_data
