"""Unit tests for audit logger."""

from unittest.mock import MagicMock, patch

import pytest

from mcp_devbench.utils.audit_logger import AuditEventType, AuditLogger, get_audit_logger


@pytest.fixture
def audit_logger():
    """Create audit logger for testing."""
    return AuditLogger()


@pytest.fixture
def mock_logger():
    """Mock logger for testing."""
    mock = MagicMock()
    with patch("mcp_devbench.utils.audit_logger.get_logger", return_value=mock):
        yield mock


def test_audit_logger_singleton():
    """Test that get_audit_logger returns singleton instance."""
    logger1 = get_audit_logger()
    logger2 = get_audit_logger()
    assert logger1 is logger2


def test_log_basic_event(mock_logger):
    """Test logging a basic event."""
    logger = AuditLogger()
    logger._logger = mock_logger

    logger.log_event(
        event_type=AuditEventType.CONTAINER_SPAWN, container_id="c_123", client_name="test_client"
    )

    # Check that info was called
    assert mock_logger.info.called
    call_args = mock_logger.info.call_args
    assert call_args[0][0] == "audit_event"
    extra = call_args[1]["extra"]
    assert extra["event_type"] == "container_spawn"
    assert extra["container_id"] == "c_123"
    assert extra["client_name"] == "test_client"


def test_log_event_with_details(mock_logger):
    """Test logging event with details."""
    logger = AuditLogger()
    logger._logger = mock_logger

    details = {"image": "ubuntu:latest", "persistent": True}

    logger.log_event(
        event_type=AuditEventType.CONTAINER_SPAWN,
        container_id="c_123",
        details=details,
    )

    call_args = mock_logger.info.call_args
    extra = call_args[1]["extra"]
    assert extra["details"]["image"] == "ubuntu:latest"
    assert extra["details"]["persistent"] is True


def test_log_event_with_correlation_id(mock_logger):
    """Test logging event with correlation ID."""
    logger = AuditLogger()
    logger._logger = mock_logger

    logger.log_event(
        event_type=AuditEventType.EXEC_START,
        container_id="c_123",
        correlation_id="req_456",
    )

    call_args = mock_logger.info.call_args
    extra = call_args[1]["extra"]
    assert extra["correlation_id"] == "req_456"


def test_log_event_with_session_id(mock_logger):
    """Test logging event with session ID."""
    logger = AuditLogger()
    logger._logger = mock_logger

    logger.log_event(
        event_type=AuditEventType.CONTAINER_ATTACH,
        container_id="c_123",
        session_id="sess_789",
    )

    call_args = mock_logger.info.call_args
    extra = call_args[1]["extra"]
    assert extra["session_id"] == "sess_789"


def test_sanitize_password(audit_logger):
    """Test that passwords are redacted."""
    details = {"username": "admin", "password": "secret123"}
    sanitized = audit_logger._sanitize_details(details)

    assert sanitized["username"] == "admin"
    assert sanitized["password"] == "***REDACTED***"


def test_sanitize_token(audit_logger):
    """Test that tokens are redacted."""
    details = {"api_token": "abc123xyz"}
    sanitized = audit_logger._sanitize_details(details)

    assert sanitized["api_token"] == "***REDACTED***"


def test_sanitize_nested_dict(audit_logger):
    """Test sanitization of nested dictionaries."""
    details = {
        "config": {"database_password": "db_secret", "host": "localhost"},
        "normal_field": "value",
    }
    sanitized = audit_logger._sanitize_details(details)

    assert sanitized["config"]["database_password"] == "***REDACTED***"
    assert sanitized["config"]["host"] == "localhost"
    assert sanitized["normal_field"] == "value"


def test_sanitize_list_of_dicts(audit_logger):
    """Test sanitization of lists containing dictionaries."""
    details = {
        "env_vars": [
            {"name": "DB_HOST", "value": "localhost"},
            {"name": "API_KEY", "password": "secret"},
        ]
    }
    sanitized = audit_logger._sanitize_details(details)

    assert sanitized["env_vars"][0]["value"] == "localhost"
    assert sanitized["env_vars"][1]["password"] == "***REDACTED***"


def test_sanitize_preserves_non_sensitive(audit_logger):
    """Test that non-sensitive data is preserved."""
    details = {
        "image": "ubuntu:latest",
        "cmd": ["echo", "hello"],
        "persistent": True,
        "count": 42,
    }
    sanitized = audit_logger._sanitize_details(details)

    assert sanitized == details


def test_log_exec_start_event(mock_logger):
    """Test logging exec start event."""
    logger = AuditLogger()
    logger._logger = mock_logger

    logger.log_event(
        event_type=AuditEventType.EXEC_START,
        container_id="c_123",
        details={"cmd": ["ls", "-la"], "as_root": False},
    )

    call_args = mock_logger.info.call_args
    extra = call_args[1]["extra"]
    assert extra["event_type"] == "exec_start"
    assert extra["details"]["cmd"] == ["ls", "-la"]


def test_log_fs_write_event(mock_logger):
    """Test logging filesystem write event."""
    logger = AuditLogger()
    logger._logger = mock_logger

    logger.log_event(
        event_type=AuditEventType.FS_WRITE,
        container_id="c_123",
        details={"path": "/workspace/file.txt", "size_bytes": 1024},
    )

    call_args = mock_logger.info.call_args
    extra = call_args[1]["extra"]
    assert extra["event_type"] == "fs_write"
    assert extra["details"]["path"] == "/workspace/file.txt"


def test_log_security_violation(mock_logger):
    """Test logging security policy violation."""
    logger = AuditLogger()
    logger._logger = mock_logger

    logger.log_event(
        event_type=AuditEventType.SECURITY_POLICY_VIOLATION,
        container_id="c_123",
        details={"violation": "disallowed_image", "image": "malicious:latest"},
    )

    call_args = mock_logger.info.call_args
    extra = call_args[1]["extra"]
    assert extra["event_type"] == "security_policy_violation"
    assert extra["details"]["violation"] == "disallowed_image"


def test_log_system_startup(mock_logger):
    """Test logging system startup event."""
    logger = AuditLogger()
    logger._logger = mock_logger

    logger.log_event(
        event_type=AuditEventType.SYSTEM_STARTUP, details={"version": "0.1.0"}
    )

    call_args = mock_logger.info.call_args
    extra = call_args[1]["extra"]
    assert extra["event_type"] == "system_startup"


def test_event_has_timestamp(mock_logger):
    """Test that all events have timestamps."""
    logger = AuditLogger()
    logger._logger = mock_logger

    logger.log_event(event_type=AuditEventType.CONTAINER_SPAWN, container_id="c_123")

    call_args = mock_logger.info.call_args
    extra = call_args[1]["extra"]
    assert "timestamp" in extra


def test_multiple_sensitive_keys(audit_logger):
    """Test handling multiple sensitive keys."""
    details = {
        "password": "secret1",
        "api_key": "secret2",
        "auth_token": "secret3",
        "private_key": "secret4",
        "credentials": "secret5",
    }
    sanitized = audit_logger._sanitize_details(details)

    for key in details.keys():
        assert sanitized[key] == "***REDACTED***"


def test_case_insensitive_sanitization(audit_logger):
    """Test that sanitization is case-insensitive."""
    details = {"PASSWORD": "secret1", "API_TOKEN": "secret2", "Secret_Key": "secret3"}
    sanitized = audit_logger._sanitize_details(details)

    assert sanitized["PASSWORD"] == "***REDACTED***"
    assert sanitized["API_TOKEN"] == "***REDACTED***"
    assert sanitized["Secret_Key"] == "***REDACTED***"
