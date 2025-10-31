"""Unit tests for SecurityManager."""

from unittest.mock import MagicMock, patch

import pytest

from mcp_devbench.managers.security_manager import (
    ResourceLimits,
    SecurityManager,
    SecurityPolicy,
)


@pytest.fixture
def security_manager():
    """Create a SecurityManager instance."""
    with patch("mcp_devbench.managers.security_manager.get_settings") as mock_settings:
        settings = MagicMock()
        mock_settings.return_value = settings
        manager = SecurityManager()
        yield manager


def test_default_security_policy():
    """Test default security policy initialization."""
    policy = SecurityPolicy()

    assert policy.default_uid == 1000
    assert policy.default_gid == 1000
    assert policy.allow_root_execution is False
    assert policy.drop_capabilities == ["ALL"]
    assert policy.read_only_rootfs is True
    assert policy.no_new_privileges is True
    assert policy.allow_network is True
    assert policy.resource_limits is not None


def test_custom_security_policy():
    """Test custom security policy."""
    limits = ResourceLimits(memory_mb=1024, cpu_quota=200000, pids_limit=512)
    policy = SecurityPolicy(
        default_uid=2000,
        default_gid=2000,
        allow_root_execution=True,
        read_only_rootfs=False,
        resource_limits=limits,
    )

    assert policy.default_uid == 2000
    assert policy.default_gid == 2000
    assert policy.allow_root_execution is True
    assert policy.read_only_rootfs is False
    assert policy.resource_limits.memory_mb == 1024
    assert policy.resource_limits.cpu_quota == 200000
    assert policy.resource_limits.pids_limit == 512


def test_resource_limits_defaults():
    """Test resource limits default values."""
    limits = ResourceLimits()

    assert limits.memory_mb == 512
    assert limits.cpu_quota == 100000
    assert limits.cpu_period == 100000
    assert limits.pids_limit == 256


def test_get_container_security_config_default(security_manager):
    """Test getting container security config with defaults."""
    config = security_manager.get_container_security_config()

    assert config["user"] == "1000:1000"
    assert config["privileged"] is False
    assert config["read_only"] is True
    assert config["cap_drop"] == ["ALL"]
    assert config["network_mode"] == "bridge"
    assert config["mem_limit"] == "512m"
    assert config["cpu_quota"] == 100000
    assert config["cpu_period"] == 100000
    assert config["pids_limit"] == 256
    assert "no-new-privileges:true" in config["security_opt"]


def test_get_container_security_config_as_root(security_manager):
    """Test getting container security config for root user."""
    config = security_manager.get_container_security_config(as_root=True)

    assert config["user"] == "0:0"
    assert config["privileged"] is False


def test_get_container_security_config_custom_policy(security_manager):
    """Test getting container security config with custom policy."""
    limits = ResourceLimits(memory_mb=1024, cpu_quota=50000, pids_limit=128)
    policy = SecurityPolicy(
        default_uid=2000,
        default_gid=2000,
        read_only_rootfs=False,
        no_new_privileges=False,
        allow_network=False,
        resource_limits=limits,
    )

    config = security_manager.get_container_security_config(custom_policy=policy)

    assert config["user"] == "2000:2000"
    assert config["read_only"] is False
    assert config["network_mode"] == "none"
    assert config["mem_limit"] == "1024m"
    assert config["cpu_quota"] == 50000
    assert config["pids_limit"] == 128
    assert "security_opt" not in config  # no_new_privileges is False


def test_get_exec_security_config_default(security_manager):
    """Test getting exec security config with defaults."""
    config = security_manager.get_exec_security_config()

    assert config["user"] == "1000"
    assert config["privileged"] is False


def test_get_exec_security_config_as_root(security_manager):
    """Test getting exec security config for root user."""
    config = security_manager.get_exec_security_config(as_root=True)

    assert config["user"] == "0"
    assert config["privileged"] is False


def test_validate_as_root_request(security_manager):
    """Test validating as_root request."""
    result = security_manager.validate_as_root_request(
        container_id="c_123",
        image="python:3.11",
        reason="Need to install system packages",
    )

    # Should allow but audit
    assert result is True


def test_audit_security_event(security_manager):
    """Test auditing security events."""
    # Should not raise any exceptions
    security_manager.audit_security_event(
        event_type="root_access_granted",
        container_id="c_123",
        details={
            "image": "python:3.11",
            "reason": "Test",
        },
    )


def test_security_config_never_privileged(security_manager):
    """Test that privileged mode is never allowed."""
    # Default config
    config = security_manager.get_container_security_config()
    assert config["privileged"] is False

    # As root
    config = security_manager.get_container_security_config(as_root=True)
    assert config["privileged"] is False

    # Custom policy with allow_root_execution
    policy = SecurityPolicy(allow_root_execution=True)
    config = security_manager.get_container_security_config(custom_policy=policy)
    assert config["privileged"] is False


def test_security_config_drops_capabilities(security_manager):
    """Test that dangerous capabilities are dropped."""
    config = security_manager.get_container_security_config()

    assert "cap_drop" in config
    assert "ALL" in config["cap_drop"]


def test_resource_limits_applied(security_manager):
    """Test that resource limits are applied correctly."""
    config = security_manager.get_container_security_config()

    # Default limits
    assert config["mem_limit"] == "512m"
    assert config["cpu_quota"] == 100000
    assert config["cpu_period"] == 100000
    assert config["pids_limit"] == 256


def test_custom_resource_limits(security_manager):
    """Test applying custom resource limits."""
    limits = ResourceLimits(
        memory_mb=2048,
        cpu_quota=200000,
        cpu_period=100000,
        pids_limit=512,
    )
    policy = SecurityPolicy(resource_limits=limits)

    config = security_manager.get_container_security_config(custom_policy=policy)

    assert config["mem_limit"] == "2048m"
    assert config["cpu_quota"] == 200000
    assert config["cpu_period"] == 100000
    assert config["pids_limit"] == 512


def test_network_control_enabled(security_manager):
    """Test network control when enabled."""
    policy = SecurityPolicy(allow_network=True)
    config = security_manager.get_container_security_config(custom_policy=policy)

    assert config["network_mode"] == "bridge"


def test_network_control_disabled(security_manager):
    """Test network control when disabled."""
    policy = SecurityPolicy(allow_network=False)
    config = security_manager.get_container_security_config(custom_policy=policy)

    assert config["network_mode"] == "none"


def test_read_only_rootfs_enabled(security_manager):
    """Test read-only root filesystem when enabled."""
    policy = SecurityPolicy(read_only_rootfs=True)
    config = security_manager.get_container_security_config(custom_policy=policy)

    assert config["read_only"] is True


def test_read_only_rootfs_disabled(security_manager):
    """Test read-only root filesystem when disabled."""
    policy = SecurityPolicy(read_only_rootfs=False)
    config = security_manager.get_container_security_config(custom_policy=policy)

    assert config["read_only"] is False


def test_no_new_privileges_enabled(security_manager):
    """Test no-new-privileges security option when enabled."""
    policy = SecurityPolicy(no_new_privileges=True)
    config = security_manager.get_container_security_config(custom_policy=policy)

    assert "security_opt" in config
    assert "no-new-privileges:true" in config["security_opt"]


def test_no_new_privileges_disabled(security_manager):
    """Test no-new-privileges security option when disabled."""
    policy = SecurityPolicy(no_new_privileges=False)
    config = security_manager.get_container_security_config(custom_policy=policy)

    # Should not have security_opt if no_new_privileges is False
    assert "security_opt" not in config
