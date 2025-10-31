"""Structured audit logging for MCP DevBench operations."""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from mcp_devbench.utils.logging import get_logger


class AuditEventType(str, Enum):
    """Types of audit events."""

    # Container events
    CONTAINER_SPAWN = "container_spawn"
    CONTAINER_ATTACH = "container_attach"
    CONTAINER_KILL = "container_kill"
    CONTAINER_STATE_CHANGE = "container_state_change"

    # Exec events
    EXEC_START = "exec_start"
    EXEC_OUTPUT = "exec_output"
    EXEC_CANCEL = "exec_cancel"
    EXEC_COMPLETE = "exec_complete"

    # Filesystem events
    FS_READ = "fs_read"
    FS_WRITE = "fs_write"
    FS_DELETE = "fs_delete"
    FS_BATCH = "fs_batch"
    FS_STAT = "fs_stat"
    FS_LIST = "fs_list"

    # Security events
    SECURITY_AS_ROOT = "security_as_root"
    SECURITY_POLICY_VIOLATION = "security_policy_violation"

    # Transfer events
    TRANSFER_EXPORT = "transfer_export"
    TRANSFER_IMPORT = "transfer_import"

    # System events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_RECONCILE = "system_reconcile"
    SYSTEM_GC = "system_gc"


class AuditLogger:
    """Structured audit logger for tracking all operations."""

    def __init__(self):
        """Initialize the audit logger."""
        self._logger = get_logger("audit")
        # Set audit logger to INFO level to ensure events are always logged
        self._logger.setLevel(logging.INFO)

    def log_event(
        self,
        event_type: AuditEventType,
        container_id: Optional[str] = None,
        client_name: Optional[str] = None,
        session_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Log an audit event.

        Args:
            event_type: Type of event being logged
            container_id: Container ID if relevant
            client_name: Name of the client performing the action
            session_id: Session ID for the action
            correlation_id: Request correlation ID
            details: Additional event-specific details
        """
        # Sanitize details to remove sensitive information
        sanitized_details = self._sanitize_details(details or {})

        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type.value,
        }

        if container_id:
            event["container_id"] = container_id
        if client_name:
            event["client_name"] = client_name
        if session_id:
            event["session_id"] = session_id
        if correlation_id:
            event["correlation_id"] = correlation_id
        if sanitized_details:
            event["details"] = sanitized_details

        self._logger.info("audit_event", extra=event)

    def _sanitize_details(self, details: dict[str, Any]) -> dict[str, Any]:
        """
        Sanitize sensitive information from event details.

        Args:
            details: Raw event details

        Returns:
            Sanitized details with sensitive fields redacted
        """
        sensitive_keys = {
            "password",
            "token",
            "secret",
            "key",
            "auth",
            "credentials",
            "private",
        }

        sanitized = {}
        for key, value in details.items():
            # Check if key contains sensitive words
            if any(sensitive_word in key.lower() for sensitive_word in sensitive_keys):
                sanitized[key] = "***REDACTED***"
            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                sanitized[key] = self._sanitize_details(value)
            elif isinstance(value, list):
                # Sanitize lists of dictionaries
                sanitized[key] = [
                    self._sanitize_details(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                sanitized[key] = value

        return sanitized


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """
    Get the global audit logger instance.

    Returns:
        AuditLogger instance
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
