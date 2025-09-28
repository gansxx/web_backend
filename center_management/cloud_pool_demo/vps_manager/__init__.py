"""
VPS Manager Package

A unified interface for managing VPS instances across multiple cloud providers.
Supports Vultr, AWS EC2, and AWS Lightsail.
"""

from .base import VPSProvider, VPSInstance, VPSConfig
from .factory import VPSFactory, get_provider, list_providers
from .exceptions import VPSError, VPSConnectionError, VPSAuthError, VPSNotFoundError

__version__ = "1.0.0"
__all__ = [
    "VPSProvider",
    "VPSInstance",
    "VPSConfig",
    "VPSFactory",
    "get_provider",
    "list_providers",
    "VPSError",
    "VPSConnectionError",
    "VPSAuthError",
    "VPSNotFoundError"
]