"""
Pydantic Models for R2 Package Management

Data models for request validation and response serialization.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
import re


class PackageStatus(str, Enum):
    """Package status enumeration"""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class HashAlgorithm(str, Enum):
    """Supported hash algorithms"""
    SHA256 = "sha256"
    MD5 = "md5"
    SHA1 = "sha1"


class PackageUploadRequest(BaseModel):
    """Request model for package upload"""
    package_name: str = Field(..., min_length=1, max_length=100, description="Package name")
    version: str = Field(..., description="Semantic version (e.g., 1.0.0)")
    description: Optional[str] = Field(None, max_length=500, description="Package description")
    tags: List[str] = Field(default_factory=list, description="Package tags")
    is_public: bool = Field(default=False, description="Whether package is publicly accessible")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @field_validator('version')
    @classmethod
    def validate_version(cls, v: str) -> str:
        """Validate semantic version format"""
        pattern = r'^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$'
        if not re.match(pattern, v):
            raise ValueError('Version must follow semantic versioning (e.g., 1.0.0, 1.0.0-alpha, 1.0.0+build)')
        return v

    @field_validator('package_name')
    @classmethod
    def validate_package_name(cls, v: str) -> str:
        """Validate package name format"""
        if not re.match(r'^[a-zA-Z0-9._-]+$', v):
            raise ValueError('Package name can only contain letters, numbers, dots, hyphens, and underscores')
        return v


class PackageUploadResponse(BaseModel):
    """Response model for package upload"""
    id: str = Field(..., description="Package UUID")
    package_name: str
    version: str
    r2_key: str = Field(..., description="R2 storage key")
    file_size: int = Field(..., description="File size in bytes")
    file_hash: str = Field(..., description="File hash")
    hash_algorithm: str
    download_url: Optional[str] = Field(None, description="Presigned download URL")
    created_at: datetime


class PackageInfo(BaseModel):
    """Package information model"""
    id: str
    package_name: str
    version: str
    r2_key: str
    file_size: int
    file_hash: str
    hash_algorithm: str
    description: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    is_public: bool
    uploader_id: str
    download_count: int
    status: PackageStatus
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class PackageListItem(BaseModel):
    """Simplified package list item"""
    id: str
    package_name: str
    version: str
    description: Optional[str] = None
    file_size: int
    download_count: int
    is_public: bool
    created_at: datetime


class PackageVersionInfo(BaseModel):
    """Package version information"""
    id: str
    version: str
    file_size: int
    download_count: int
    status: PackageStatus
    created_at: datetime


class PackageSearchRequest(BaseModel):
    """Request model for package search"""
    search_term: Optional[str] = Field(None, description="Search term for name/description")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    is_public: Optional[bool] = Field(None, description="Filter by public status")
    limit: int = Field(50, ge=1, le=100, description="Results per page")
    offset: int = Field(0, ge=0, description="Pagination offset")


class PackageSearchResponse(BaseModel):
    """Response model for package search"""
    results: List[PackageListItem]
    total: int
    limit: int
    offset: int


class PackageDownloadRequest(BaseModel):
    """Request model for package download"""
    expiration: int = Field(3600, ge=60, le=86400, description="URL expiration in seconds")
    use_public_domain: bool = Field(True, description="Use custom public domain if configured")


class PackageDownloadResponse(BaseModel):
    """Response model for package download"""
    package_name: str
    version: str
    download_url: str
    expires_in: int
    file_size: int
    file_hash: str


class PackageUpdateRequest(BaseModel):
    """Request model for package update"""
    description: Optional[str] = Field(None, max_length=500)
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None
    status: Optional[PackageStatus] = None
    metadata: Optional[Dict[str, Any]] = None


class PackageStatsResponse(BaseModel):
    """Response model for package statistics"""
    package_name: str
    total_versions: int
    total_downloads: int
    total_size_bytes: int
    total_size_mb: float
    latest_version: Optional[str]
    latest_upload_date: Optional[datetime]


class StorageStatsResponse(BaseModel):
    """Response model for storage statistics"""
    total_packages: int
    total_versions: int
    total_downloads: int
    total_size_bytes: int
    total_size_mb: float
    total_size_gb: float
    bucket_name: str


class PackageVersionListRequest(BaseModel):
    """Request model for listing package versions"""
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class PackageVersionListResponse(BaseModel):
    """Response model for package versions"""
    package_name: str
    versions: List[PackageVersionInfo]
    total: int
    limit: int
    offset: int


class PackageDeleteResponse(BaseModel):
    """Response model for package deletion"""
    message: str
    package_name: str
    version: str
    deleted_at: datetime


class BulkDeleteRequest(BaseModel):
    """Request model for bulk package deletion"""
    package_ids: List[str] = Field(..., min_length=1, max_length=50)


class BulkDeleteResponse(BaseModel):
    """Response model for bulk deletion"""
    deleted_count: int
    failed_count: int
    errors: List[Dict[str, str]] = Field(default_factory=list)


class CleanupRequest(BaseModel):
    """Request model for cleanup old packages"""
    days_threshold: int = Field(90, ge=1, le=365, description="Archive age threshold in days")
    dry_run: bool = Field(True, description="Dry run mode (preview only)")


class CleanupResponse(BaseModel):
    """Response model for cleanup operation"""
    packages_marked: int
    dry_run: bool
    packages: List[Dict[str, str]] = Field(default_factory=list)


class DownloadHistoryItem(BaseModel):
    """Download history item"""
    id: str
    package_id: str
    package_name: str
    version: str
    user_id: Optional[str]
    ip_address: Optional[str]
    downloaded_at: datetime


class DownloadHistoryResponse(BaseModel):
    """Response model for download history"""
    package_name: str
    version: str
    downloads: List[DownloadHistoryItem]
    total: int
    limit: int
    offset: int


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    r2_connection: bool
    database_connection: bool
    timestamp: datetime


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
