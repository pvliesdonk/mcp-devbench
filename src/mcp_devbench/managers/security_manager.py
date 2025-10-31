"""Security controls and policies for containers."""

from dataclasses import dataclass
from typing import Dict, List, Optional

from mcp_devbench.config import get_settings
from mcp_devbench.utils import get_logger

logger = get_logger(__name__)


@dataclass
class ResourceLimits:
    """Resource limits for container."""

    memory_mb: Optional[int] = 512  # 512MB default
    cpu_quota: Optional[int] = 100000  # 100% of one CPU (100000 = 1 CPU in microseconds per 100ms period)
    cpu_period: Optional[int] = 100000  # 100ms period
    pids_limit: Optional[int] = 256  # Max number of processes


@dataclass
class SecurityPolicy:
    """Security policy for container operations."""

    # User management
    default_uid: int = 1000
    default_gid: int = 1000
    allow_root_execution: bool = False
    
    # Container security
    drop_capabilities: List[str] = None
    read_only_rootfs: bool = True
    no_new_privileges: bool = True
    
    # Network
    allow_network: bool = True
    
    # Resource limits
    resource_limits: ResourceLimits = None

    def __post_init__(self):
        """Initialize default values after instantiation."""
        if self.drop_capabilities is None:
            # Drop all capabilities by default, which is the most secure
            # Users can be given specific capabilities if needed
            self.drop_capabilities = ["ALL"]
        
        if self.resource_limits is None:
            self.resource_limits = ResourceLimits()


class SecurityManager:
    """Manager for security controls and policies."""

    def __init__(self) -> None:
        """Initialize security manager."""
        self.settings = get_settings()
        self._default_policy = SecurityPolicy()

    def get_container_security_config(
        self,
        as_root: bool = False,
        custom_policy: Optional[SecurityPolicy] = None,
    ) -> Dict:
        """
        Get Docker container security configuration.

        Args:
            as_root: Whether to run as root user
            custom_policy: Optional custom security policy

        Returns:
            Dictionary of Docker security parameters
        """
        policy = custom_policy or self._default_policy

        config = {}

        # User configuration
        if as_root:
            logger.warning(
                "Container will run as root",
                extra={"security_warning": "privileged_execution"},
            )
            config["user"] = "0:0"
        else:
            config["user"] = f"{policy.default_uid}:{policy.default_gid}"

        # Security options
        security_opt = []
        
        if policy.no_new_privileges:
            security_opt.append("no-new-privileges:true")
        
        if security_opt:
            config["security_opt"] = security_opt

        # Capabilities - drop dangerous ones
        if policy.drop_capabilities:
            config["cap_drop"] = policy.drop_capabilities

        # Read-only root filesystem (except /workspace which is mounted)
        config["read_only"] = policy.read_only_rootfs

        # Never allow privileged mode
        config["privileged"] = False

        # Network mode
        if policy.allow_network:
            config["network_mode"] = "bridge"
        else:
            config["network_mode"] = "none"

        # Resource limits
        if policy.resource_limits:
            limits = policy.resource_limits
            
            if limits.memory_mb:
                # Memory limit in bytes
                config["mem_limit"] = f"{limits.memory_mb}m"
            
            if limits.cpu_quota and limits.cpu_period:
                # CPU quota (microseconds per period)
                config["cpu_quota"] = limits.cpu_quota
                config["cpu_period"] = limits.cpu_period
            
            if limits.pids_limit:
                # PID limit
                config["pids_limit"] = limits.pids_limit

        logger.debug(
            "Generated container security config",
            extra={
                "as_root": as_root,
                "read_only": config.get("read_only"),
                "cap_drop": config.get("cap_drop"),
                "memory_limit": config.get("mem_limit"),
            },
        )

        return config

    def get_exec_security_config(self, as_root: bool = False) -> Dict:
        """
        Get Docker exec security configuration.

        Args:
            as_root: Whether to run as root user

        Returns:
            Dictionary of Docker exec parameters
        """
        config = {}

        if as_root:
            logger.warning(
                "Exec will run as root",
                extra={"security_warning": "privileged_execution"},
            )
            config["user"] = "0"
        else:
            config["user"] = str(self._default_policy.default_uid)

        # Never allow privileged mode
        config["privileged"] = False

        return config

    def validate_as_root_request(
        self,
        container_id: str,
        image: str,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Validate a request to run as root.

        Args:
            container_id: Container ID
            image: Container image
            reason: Optional reason for root access

        Returns:
            True if allowed, False otherwise
        """
        # For now, allow root execution but log it
        # In production, this could check against an allow-list
        logger.warning(
            "Root execution requested",
            extra={
                "container_id": container_id,
                "image": image,
                "reason": reason,
                "security_event": "root_access_requested",
            },
        )

        # Future enhancement: Check image against root allow-list
        # For now, allow but audit
        return True

    def audit_security_event(
        self,
        event_type: str,
        container_id: str,
        details: Optional[Dict] = None,
    ) -> None:
        """
        Audit a security-relevant event.

        Args:
            event_type: Type of security event
            container_id: Container ID
            details: Additional event details
        """
        log_data = {
            "security_event": event_type,
            "container_id": container_id,
        }

        if details:
            log_data.update(details)

        logger.info("Security event", extra=log_data)


# Singleton instance
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """Get the security manager singleton."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager
