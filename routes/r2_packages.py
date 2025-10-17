"""
R2 Package Management API Routes

FastAPI routes for R2 package distribution and management.

Access Control:
- Download endpoint: External access allowed (public packages: no auth, private packages: require auth)
- All other endpoints: Localhost-only access (no authentication required)
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

from center_management.r2_storage import (
    PackageManager,
    PackageUploadRequest,
    PackageUploadResponse,
    PackageSearchRequest,
    PackageSearchResponse,
    PackageDownloadRequest,
    PackageDownloadResponse,
    PackageUpdateRequest,
    PackageStatsResponse,
    StorageStatsResponse,
    PackageVersionListRequest,
    PackageVersionListResponse,
    PackageDeleteResponse,
    CleanupRequest,
    CleanupResponse,
    ErrorResponse,
    R2ValidationError,
    R2NotFoundError,
    R2UploadError,
    R2StorageError
)
from datetime import datetime

router = APIRouter(prefix="/r2/packages", tags=["r2-packages"])


def _require_package_manager(request: Request) -> PackageManager:
    """Get PackageManager instance from app state"""
    pm = getattr(request.app.state, "package_manager", None)
    if not pm:
        raise HTTPException(500, detail="Package manager not initialized")
    return pm


def _require_localhost_access(request: Request) -> None:
    """Require request from localhost, raise 403 if not"""
    client_host = request.client.host if request.client else None

    # Allow localhost, 127.0.0.1, ::1 (IPv6 localhost)
    allowed_hosts = ['localhost', '127.0.0.1', '::1']

    if client_host not in allowed_hosts:
        logger.warning(f"Non-localhost access attempt from IP: {client_host}")
        raise HTTPException(
            403,
            detail="This endpoint is only accessible from localhost"
        )


def _get_current_user_id(request: Request) -> Optional[str]:
    """
    Extract current user ID from session/token

    Only used for download endpoint to support private package access.
    """
    supabase = getattr(request.app.state, "supabase", None)
    if not supabase:
        return None

    # Try to get user from access_token cookie or header
    access_token = request.cookies.get('access_token') or request.headers.get('authorization', '').replace('Bearer ', '')

    if not access_token:
        return None

    try:
        user_response = supabase.auth.get_user(access_token)
        user = getattr(user_response, "user", None)
        return user.id if user else None
    except:
        return None


@router.post("/upload", response_model=PackageUploadResponse)
async def upload_package(
    file: UploadFile = File(...),
    package_name: str = Form(...),
    version: str = Form(...),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),  # Comma-separated
    is_public: bool = Form(False),
    uploader_id: Optional[str] = Form(None),
    request: Request = None
):
    """
    Upload a new package version

    **RESTRICTED TO LOCALHOST ONLY**

    Only accessible from localhost (127.0.0.1, ::1). External clients cannot upload packages.
    Uploaded file is stored in R2 and metadata in database.
    """
    try:
        # Check localhost access
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        # Validate required fields
        if not package_name or not version:
            raise HTTPException(400, detail="package_name and version are required")

        # Use provided uploader_id or fallback to system ID
        if not uploader_id:
            # System uploader ID for packages uploaded via localhost without explicit user
            uploader_id = "00000000-0000-0000-0000-000000000000"
            logger.warning(f"No uploader_id provided, using system default for package: {package_name} v{version}")
        else:
            logger.info(f"Using provided uploader_id: {uploader_id} for package: {package_name} v{version}")

        # Parse tags
        tags_list = [t.strip() for t in tags.split(',')] if tags else []

        # Upload package
        result = pm.upload_package(
            package_name=package_name,
            version=version,
            file_obj=file.file,
            uploader_id=uploader_id,
            description=description,
            tags=tags_list,
            is_public=is_public,
            content_type=file.content_type
        )

        return PackageUploadResponse(
            id=result['id'],
            package_name=result['package_name'],
            version=result['version'],
            r2_key=result['r2_key'],
            file_size=result['file_size'],
            file_hash=result['file_hash'],
            hash_algorithm=result['hash_algorithm'],
            created_at=result['created_at']
        )

    except R2ValidationError as e:
        raise HTTPException(400, detail=str(e))
    except R2UploadError as e:
        raise HTTPException(500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(500, detail="Upload failed")


@router.get("/{package_name}/{version}/download", response_model=PackageDownloadResponse)
async def download_package(
    package_name: str,
    version: str,
    expiration: int = 3600,
    use_public_domain: bool = True,
    request: Request = None
):
    """
    Generate presigned download URL for package

    **EXTERNAL ACCESS ALLOWED**

    This is the ONLY endpoint accessible from external networks.
    - Public packages: Accessible without authentication
    - Private packages: Require authentication (access_token)
    """
    try:
        pm = _require_package_manager(request)
        user_id = _get_current_user_id(request)

        # Get package info to check visibility
        package = pm.get_package_info(package_name, version)
        if not package:
            raise HTTPException(404, detail="Package not found")

        # Check access permission
        if not package['is_public']:
            if not user_id:
                raise HTTPException(401, detail="Authentication required for private packages")
            # Could add additional permission checks here

        # Get client IP and user agent for tracking
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get('user-agent')

        # Generate download URL
        result = pm.download_package(
            package_name=package_name,
            version=version,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            expiration=expiration,
            use_public_domain=use_public_domain
        )

        return PackageDownloadResponse(**result)

    except R2NotFoundError:
        raise HTTPException(404, detail="Package not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download URL generation failed: {e}")
        raise HTTPException(500, detail="Failed to generate download URL")



@router.get("/{package_name}/versions", response_model=PackageVersionListResponse)
async def list_package_versions(
    package_name: str,
    limit: int = 20,
    offset: int = 0,
    request: Request = None
):
    """
    List all versions of a package

    **LOCALHOST ONLY** - No authentication required
    """
    try:
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        result = pm.list_package_versions(package_name, limit, offset)

        return PackageVersionListResponse(**result)

    except Exception as e:
        logger.error(f"List versions failed: {e}")
        raise HTTPException(500, detail="Failed to list package versions")


@router.post("/search", response_model=PackageSearchResponse)
async def search_packages(
    search_request: PackageSearchRequest,
    request: Request = None
):
    """
    Search packages by name, description, or tags

    **LOCALHOST ONLY** - No authentication required
    """
    try:
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        result = pm.search_packages(
            search_term=search_request.search_term,
            tags=search_request.tags,
            is_public=search_request.is_public,
            limit=search_request.limit,
            offset=search_request.offset
        )

        return PackageSearchResponse(**result)

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(500, detail="Search failed")


@router.get("/public")
async def list_public_packages(
    limit: int = 50,
    offset: int = 0,
    request: Request = None
):
    """
    List all public packages

    **LOCALHOST ONLY** - No authentication required
    """
    try:
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        result = pm.search_packages(
            is_public=True,
            limit=limit,
            offset=offset
        )

        return result

    except Exception as e:
        logger.error(f"List public packages failed: {e}")
        raise HTTPException(500, detail="Failed to list public packages")


@router.get("/my-uploads")
async def list_my_packages(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    request: Request = None
):
    """
    List packages uploaded by specific user

    **LOCALHOST ONLY** - No authentication required

    Args:
        user_id: UUID of the user whose packages to list
    """
    try:
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        db = pm.db
        packages = db.list_user_packages(user_id, limit, offset)

        return {
            'packages': packages,
            'total': len(packages),
            'limit': limit,
            'offset': offset
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List user packages failed: {e}")
        raise HTTPException(500, detail="Failed to list user packages")


@router.patch("/{package_name}/{version}")
async def update_package(
    package_name: str,
    version: str,
    update_request: PackageUpdateRequest,
    request: Request = None
):
    """
    Update package metadata

    **LOCALHOST ONLY** - No authentication required
    """
    try:
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        # Build updates dict
        updates = {}
        if update_request.description is not None:
            updates['description'] = update_request.description
        if update_request.tags is not None:
            updates['tags'] = update_request.tags
        if update_request.is_public is not None:
            updates['is_public'] = update_request.is_public
        if update_request.status is not None:
            updates['status'] = update_request.status
        if update_request.metadata is not None:
            updates['metadata'] = update_request.metadata

        # Call PackageManager without user_id (will be modified next)
        updated = pm.update_package_metadata(
            package_name=package_name,
            version=version,
            **updates
        )

        if not updated:
            raise HTTPException(404, detail="Package not found or update failed")

        return updated

    except R2ValidationError as e:
        raise HTTPException(403, detail=str(e))
    except R2NotFoundError:
        raise HTTPException(404, detail="Package not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update package failed: {e}")
        raise HTTPException(500, detail="Failed to update package")


@router.delete("/{package_name}/{version}", response_model=PackageDeleteResponse)
async def delete_package(
    package_name: str,
    version: str,
    hard_delete: bool = False,
    request: Request = None
):
    """
    Delete package

    **LOCALHOST ONLY** - No authentication required

    By default performs soft delete (marks as deleted).
    Use hard_delete=true to permanently remove from storage.
    """
    try:
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        # Call PackageManager without user_id (will be modified next)
        success = pm.delete_package(
            package_name=package_name,
            version=version,
            hard_delete=hard_delete
        )

        if not success:
            raise HTTPException(500, detail="Delete failed")

        return PackageDeleteResponse(
            message="Package deleted successfully",
            package_name=package_name,
            version=version,
            deleted_at=datetime.utcnow()
        )

    except R2ValidationError as e:
        raise HTTPException(403, detail=str(e))
    except R2NotFoundError:
        raise HTTPException(404, detail="Package not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete package failed: {e}")
        raise HTTPException(500, detail="Failed to delete package")


@router.get("/stats/storage", response_model=StorageStatsResponse)
async def get_storage_stats(request: Request = None):
    """
    Get overall storage statistics

    **LOCALHOST ONLY** - No authentication required
    """
    try:
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        stats = pm.get_storage_stats()

        return StorageStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Get storage stats failed: {e}")
        raise HTTPException(500, detail="Failed to retrieve storage statistics")


@router.get("/stats/{package_name}", response_model=PackageStatsResponse)
async def get_package_stats(
    package_name: str,
    request: Request = None
):
    """
    Get statistics for specific package

    **LOCALHOST ONLY** - No authentication required
    """
    try:
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        stats = pm.get_package_stats(package_name)

        if not stats:
            raise HTTPException(404, detail="Package not found")

        return PackageStatsResponse(**stats[0])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get package stats failed: {e}")
        raise HTTPException(500, detail="Failed to retrieve package statistics")


@router.post("/cleanup", response_model=CleanupResponse)
async def cleanup_old_packages(
    cleanup_request: CleanupRequest,
    request: Request = None
):
    """
    Clean up old archived packages

    **LOCALHOST ONLY** - No authentication required

    Use dry_run=true to preview before executing.
    """
    try:
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        result = pm.cleanup_old_packages(
            days_threshold=cleanup_request.days_threshold,
            dry_run=cleanup_request.dry_run
        )

        return CleanupResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        raise HTTPException(500, detail="Cleanup operation failed")


@router.get("/{package_name}/{version}/verify")
async def verify_package_integrity(
    package_name: str,
    version: str,
    request: Request = None
):
    """
    Verify package file integrity

    **LOCALHOST ONLY** - No authentication required
    """
    try:
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        is_valid = pm.verify_package_integrity(package_name, version)

        return {
            'package_name': package_name,
            'version': version,
            'integrity_verified': is_valid,
            'timestamp': datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Integrity verification failed: {e}")
        raise HTTPException(500, detail="Integrity verification failed")


@router.get("/health")
async def health_check(request: Request = None):
    """
    Health check endpoint

    **LOCALHOST ONLY** - No authentication required
    """
    try:
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        # Test R2 connection
        r2_ok = False
        try:
            pm.r2_client.list_files(max_keys=1)
            r2_ok = True
        except:
            pass

        # Test database connection
        db_ok = False
        try:
            pm.db.get_storage_stats()
            db_ok = True
        except:
            pass

        status = "healthy" if (r2_ok and db_ok) else "degraded"

        return {
            'status': status,
            'r2_connection': r2_ok,
            'database_connection': db_ok,
            'timestamp': datetime.utcnow()
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'status': 'unhealthy',
            'r2_connection': False,
            'database_connection': False,
            'timestamp': datetime.utcnow(),
            'error': str(e)
        }
@router.get("/{package_name}/{version}")
async def get_package_info(
    package_name: str,
    version: str,
    request: Request = None
):
    """
    Get detailed package information

    **LOCALHOST ONLY** - No authentication required
    """
    try:
        _require_localhost_access(request)
        pm = _require_package_manager(request)

        package = pm.get_package_info(package_name, version)

        if not package:
            raise HTTPException(404, detail="Package not found")

        return package

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get package info failed: {e}")
        raise HTTPException(500, detail="Failed to retrieve package information")

