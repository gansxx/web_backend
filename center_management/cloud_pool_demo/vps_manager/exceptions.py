"""
VPS Manager Exceptions

Custom exception classes for VPS management operations.
"""


class VPSError(Exception):
    """Base exception for VPS operations"""
    pass


class VPSConnectionError(VPSError):
    """Exception raised when connection to VPS provider fails"""
    pass


class VPSAuthError(VPSError):
    """Exception raised when authentication to VPS provider fails"""
    pass


class VPSNotFoundError(VPSError):
    """Exception raised when VPS instance is not found"""
    pass


class VPSOperationError(VPSError):
    """Exception raised when VPS operation fails"""
    pass


class VPSConfigError(VPSError):
    """Exception raised when VPS configuration is invalid"""
    pass