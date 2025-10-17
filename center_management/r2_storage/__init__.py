"""
R2 Storage Package

Cloudflare R2 storage management system for software package distribution.
"""

from .client import R2Client
from .package_manager import PackageManager
from .models import (
    PackageStatus,
    HashAlgorithm,
    PackageUploadRequest,
    PackageUploadResponse,
    PackageInfo,
    PackageListItem,
    PackageSearchRequest,
    PackageSearchResponse,
    PackageDownloadRequest,
    PackageDownloadResponse,
    PackageUpdateRequest,
    PackageStatsResponse,
    PackageVersionListRequest,
    PackageVersionListResponse,
    PackageDeleteResponse,
    BulkDeleteRequest,
    BulkDeleteResponse,
    CleanupRequest,
    CleanupResponse,
    DownloadHistoryResponse,
    HealthCheckResponse,
    StorageStatsResponse,
    ErrorResponse
)
from .exceptions import (
    R2StorageError,
    R2ConnectionError,
    R2AuthenticationError,
    R2UploadError,
    R2DownloadError,
    R2DeleteError,
    R2NotFoundError,
    R2ValidationError,
    R2QuotaExceededError,
    R2ConfigurationError
)

__all__ = [
    # Core classes
    'R2Client',
    'PackageManager',

    # Enums
    'PackageStatus',
    'HashAlgorithm',

    # Request/Response models
    'PackageUploadRequest',
    'PackageUploadResponse',
    'PackageInfo',
    'PackageListItem',
    'PackageSearchRequest',
    'PackageSearchResponse',
    'PackageDownloadRequest',
    'PackageDownloadResponse',
    'PackageUpdateRequest',
    'PackageStatsResponse',
    'PackageVersionListRequest',
    'PackageVersionListResponse',
    'PackageDeleteResponse',
    'BulkDeleteRequest',
    'BulkDeleteResponse',
    'CleanupRequest',
    'CleanupResponse',
    'DownloadHistoryResponse',
    'HealthCheckResponse',
    'StorageStatsResponse',
    'ErrorResponse',

    # Exceptions
    'R2StorageError',
    'R2ConnectionError',
    'R2AuthenticationError',
    'R2UploadError',
    'R2DownloadError',
    'R2DeleteError',
    'R2NotFoundError',
    'R2ValidationError',
    'R2QuotaExceededError',
    'R2ConfigurationError',
]

__version__ = '1.0.0'
