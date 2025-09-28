"""
Cloud Pool Demo - Multi-Cloud VPS Management System

This package contains the multi-cloud VPS management system that was moved from center_management.
It provides unified interfaces for managing VPS instances across multiple cloud providers.
"""

from .node_manage_v2 import EnhancedNodeProxy, CloudVPSManager, NodeProxy
from .vps_manager import get_provider, list_providers, VPSConfig, VPSInstance

__version__ = "1.0.0"
__all__ = [
    "EnhancedNodeProxy",
    "CloudVPSManager",
    "NodeProxy",
    "get_provider",
    "list_providers",
    "VPSConfig",
    "VPSInstance"
]