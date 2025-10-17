"""
R2 Storage Exceptions

Custom exception classes for Cloudflare R2 storage operations.
"""


class R2StorageError(Exception):
    """Base exception for R2 storage operations"""
    pass


class R2ConnectionError(R2StorageError):
    """Exception raised when connection to R2 fails"""
    pass


class R2AuthenticationError(R2StorageError):
    """Exception raised when R2 authentication fails"""
    pass


class R2UploadError(R2StorageError):
    """Exception raised when file upload fails"""
    pass


class R2DownloadError(R2StorageError):
    """Exception raised when file download fails"""
    pass


class R2DeleteError(R2StorageError):
    """Exception raised when file deletion fails"""
    pass


class R2NotFoundError(R2StorageError):
    """Exception raised when requested object is not found"""
    pass


class R2ValidationError(R2StorageError):
    """Exception raised when validation fails"""
    pass


class R2QuotaExceededError(R2StorageError):
    """Exception raised when storage quota is exceeded"""
    pass


class R2ConfigurationError(R2StorageError):
    """Exception raised when R2 configuration is invalid"""
    pass
