"""
Base classes for VPS management

Defines abstract base classes and data structures for VPS providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Union
from enum import Enum


class VPSStatus(Enum):
    """VPS instance status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    STOPPING = "stopping"
    STARTING = "starting"
    REBOOTING = "rebooting"
    UNKNOWN = "unknown"


@dataclass
class VPSInstance:
    """
    Unified VPS instance data structure
    """
    id: str
    name: str
    status: VPSStatus
    ip_address: Optional[str] = None
    private_ip: Optional[str] = None
    region: Optional[str] = None
    instance_type: Optional[str] = None
    os: Optional[str] = None
    created_at: Optional[str] = None
    provider_data: Optional[Dict[str, Any]] = None  # Provider-specific data

    def to_dict(self) -> Dict[str, Any]:
        """Convert instance to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'status': self.status.value if isinstance(self.status, VPSStatus) else self.status,
            'ip_address': self.ip_address,
            'private_ip': self.private_ip,
            'region': self.region,
            'instance_type': self.instance_type,
            'os': self.os,
            'created_at': self.created_at,
            'provider_data': self.provider_data
        }


@dataclass
class VPSConfig:
    """
    Unified VPS configuration structure
    """
    region: str
    instance_type: str
    name: str
    os_id: Union[str, int]
    ssh_key_id: Optional[Union[str, List[str]]] = None
    user_data: Optional[str] = None
    script_id: Optional[str] = None
    backup_enabled: bool = False
    monitoring_enabled: bool = False
    tags: Optional[Dict[str, str]] = None
    security_groups: Optional[List[str]] = None
    subnet_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary"""
        return {
            'region': self.region,
            'instance_type': self.instance_type,
            'name': self.name,
            'os_id': self.os_id,
            'ssh_key_id': self.ssh_key_id,
            'user_data': self.user_data,
            'script_id': self.script_id,
            'backup_enabled': self.backup_enabled,
            'monitoring_enabled': self.monitoring_enabled,
            'tags': self.tags,
            'security_groups': self.security_groups,
            'subnet_id': self.subnet_id
        }


class VPSProvider(ABC):
    """
    Abstract base class for VPS providers

    All VPS provider implementations must inherit from this class
    and implement all abstract methods.
    """

    def __init__(self, credentials: Dict[str, str], region: Optional[str] = None):
        """
        Initialize VPS provider

        Args:
            credentials: Provider-specific credentials
            region: Default region for operations
        """
        self.credentials = credentials
        self.default_region = region
        self._client = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the name of the provider"""
        pass

    @abstractmethod
    def _initialize_client(self) -> Any:
        """Initialize and return the provider's client"""
        pass

    @property
    def client(self) -> Any:
        """Get or create the provider client"""
        if self._client is None:
            self._client = self._initialize_client()
        return self._client

    @abstractmethod
    def create_instance(self, config: VPSConfig) -> str:
        """
        Create a new VPS instance

        Args:
            config: VPS configuration

        Returns:
            Instance ID
        """
        pass

    @abstractmethod
    def delete_instance(self, instance_id: str) -> bool:
        """
        Delete a VPS instance

        Args:
            instance_id: ID of the instance to delete

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def reboot_instance(self, instance_id: str) -> bool:
        """
        Reboot a VPS instance

        Args:
            instance_id: ID of the instance to reboot

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def start_instance(self, instance_id: str) -> bool:
        """
        Start a VPS instance

        Args:
            instance_id: ID of the instance to start

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def stop_instance(self, instance_id: str) -> bool:
        """
        Stop a VPS instance

        Args:
            instance_id: ID of the instance to stop

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_instance(self, instance_id: str) -> Optional[VPSInstance]:
        """
        Get information about a specific VPS instance

        Args:
            instance_id: ID of the instance

        Returns:
            VPSInstance object or None if not found
        """
        pass

    @abstractmethod
    def list_instances(self) -> List[VPSInstance]:
        """
        List all VPS instances

        Returns:
            List of VPSInstance objects
        """
        pass

    @abstractmethod
    def get_instance_ip(self, instance_id: str) -> Optional[str]:
        """
        Get the public IP address of an instance

        Args:
            instance_id: ID of the instance

        Returns:
            IP address or None if not available
        """
        pass

    @abstractmethod
    def list_regions(self) -> List[Dict[str, str]]:
        """
        List available regions

        Returns:
            List of region information
        """
        pass

    @abstractmethod
    def list_instance_types(self, region: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available instance types

        Args:
            region: Region to get instance types for (optional)

        Returns:
            List of instance type information
        """
        pass

    @abstractmethod
    def list_operating_systems(self) -> List[Dict[str, Any]]:
        """
        List available operating systems

        Returns:
            List of OS information
        """
        pass

    def wait_for_instance_state(self, instance_id: str, target_state: VPSStatus,
                              timeout: int = 300, check_interval: int = 10) -> bool:
        """
        Wait for an instance to reach a specific state

        Args:
            instance_id: ID of the instance
            target_state: Target state to wait for
            timeout: Maximum time to wait in seconds
            check_interval: Time between checks in seconds

        Returns:
            True if target state reached, False if timeout
        """
        import time
        start_time = time.time()

        while time.time() - start_time < timeout:
            instance = self.get_instance(instance_id)
            if instance and instance.status == target_state:
                return True
            time.sleep(check_interval)

        return False