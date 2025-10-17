"""
R2 Package Manager

Core business logic for R2 package management operations.
Coordinates between R2 storage client and database operations.
"""

import os
from typing import Optional, Dict, Any, BinaryIO, Union
from pathlib import Path
from datetime import datetime
from loguru import logger

from .client import R2Client
from .exceptions import (
    R2StorageError,
    R2ValidationError,
    R2UploadError,
    R2NotFoundError
)
from ..db.r2_package import R2PackageConfig


class PackageManager:
    """
    R2 Package Manager

    High-level interface for package management operations.
    Handles coordination between storage and database layers.
    """

    def __init__(
        self,
        r2_client: Optional[R2Client] = None,
        db_config: Optional[R2PackageConfig] = None
    ):
        """
        Initialize package manager

        Args:
            r2_client: Optional R2 client instance
            db_config: Optional database config instance
        """
        self.r2_client = r2_client or R2Client()
        self.db = db_config or R2PackageConfig()

        # Configuration from environment
        self.max_package_size = int(os.getenv('R2_MAX_PACKAGE_SIZE_MB', '500')) * 1024 * 1024
        self.download_url_expiry = int(os.getenv('R2_DOWNLOAD_URL_EXPIRY_SECONDS', '3600'))

        logger.info("PackageManager initialized successfully")

    def upload_package(
        self,
        package_name: str,
        version: str,
        file_obj: Union[BinaryIO, str, Path],
        uploader_id: str,
        description: Optional[str] = None,
        tags: Optional[list[str]] = None,
        is_public: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload package to R2 and create database record

        Args:
            package_name: Package name
            version: Semantic version
            file_obj: File path or file-like object
            uploader_id: User ID of uploader
            description: Optional description
            tags: Optional list of tags
            is_public: Whether package is public
            metadata: Optional metadata
            content_type: Optional content type

        Returns:
            Package information dict
        """
        try:
            # Check if package version already exists
            if self.db.check_package_exists(package_name, version):
                raise R2ValidationError(f"Package {package_name} v{version} already exists")

            # Validate file size if it's a path
            if isinstance(file_obj, (str, Path)):
                file_path = Path(file_obj)
                if not file_path.exists():
                    raise R2ValidationError(f"File not found: {file_path}")

                file_size = file_path.stat().st_size
                if file_size > self.max_package_size:
                    max_mb = self.max_package_size / (1024 * 1024)
                    raise R2ValidationError(
                        f"File size ({file_size / (1024 * 1024):.2f}MB) exceeds maximum ({max_mb}MB)"
                    )

            # Generate R2 key
            r2_key = self._generate_r2_key(package_name, version)

            # Prepare metadata for R2
            r2_metadata = {
                'package_name': package_name,
                'version': version,
                'uploader_id': uploader_id
            }
            if metadata:
                r2_metadata.update(metadata)

            # Upload to R2
            if isinstance(file_obj, (str, Path)):
                upload_result = self.r2_client.upload_file(
                    file_path=file_obj,
                    r2_key=r2_key,
                    metadata=r2_metadata,
                    content_type=content_type
                )
            else:
                upload_result = self.r2_client.upload_fileobj(
                    file_obj=file_obj,
                    r2_key=r2_key,
                    metadata=r2_metadata,
                    content_type=content_type
                )

            # Create database record
            db_record = self.db.create_package(
                package_name=package_name,
                version=version,
                r2_key=r2_key,
                file_size=upload_result['file_size'],
                file_hash=upload_result['file_hash'],
                hash_algorithm=upload_result['hash_algorithm'],
                uploader_id=uploader_id,
                description=description,
                tags=tags,
                is_public=is_public,
                metadata=metadata
            )

            logger.info(f"Successfully uploaded package {package_name} v{version}")

            return {
                'id': db_record['id'],
                'package_name': package_name,
                'version': version,
                'r2_key': r2_key,
                'file_size': upload_result['file_size'],
                'file_hash': upload_result['file_hash'],
                'hash_algorithm': upload_result['hash_algorithm'],
                'created_at': db_record['created_at']
            }

        except R2ValidationError:
            raise
        except Exception as e:
            logger.error(f"Failed to upload package {package_name} v{version}: {e}")
            # Attempt cleanup if R2 upload succeeded but DB failed
            try:
                if 'r2_key' in locals():
                    self.r2_client.delete_file(r2_key)
            except:
                pass
            raise R2UploadError(f"Package upload failed: {e}")

    def download_package(
        self,
        package_name: str,
        version: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        expiration: Optional[int] = None,
        use_public_domain: bool = True
    ) -> Dict[str, Any]:
        """
        Generate download URL for package

        Args:
            package_name: Package name
            version: Package version
            user_id: Optional user ID for tracking
            ip_address: Optional IP for tracking
            user_agent: Optional user agent for tracking
            expiration: URL expiration in seconds
            use_public_domain: Use custom public domain

        Returns:
            Download information dict
        """
        try:
            # Get package from database
            package = self.db.get_package(package_name, version)
            if not package:
                raise R2NotFoundError(f"Package {package_name} v{version} not found")

            # Verify file exists in R2
            if not self.r2_client.file_exists(package['r2_key']):
                logger.error(f"Package exists in DB but not in R2: {package['r2_key']}")
                raise R2NotFoundError(f"Package file not found in storage")

            # Generate presigned URL
            expiry = expiration or self.download_url_expiry
            download_url = self.r2_client.generate_presigned_url(
                r2_key=package['r2_key'],
                expiration=expiry,
                use_public_domain=use_public_domain
            )

            # Record download
            self.db.record_download(
                package_id=package['id'],
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent
            )

            logger.info(f"Generated download URL for {package_name} v{version}")

            return {
                'package_name': package_name,
                'version': version,
                'download_url': download_url,
                'expires_in': expiry,
                'file_size': package['file_size'],
                'file_hash': package['file_hash']
            }

        except R2NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate download URL: {e}")
            raise R2StorageError(f"Download preparation failed: {e}")

    def delete_package(
        self,
        package_name: str,
        version: str,
        hard_delete: bool = False
    ) -> bool:
        """
        Delete package from storage and database

        **LOCALHOST ONLY** - No permission check required

        Args:
            package_name: Package name
            version: Package version
            hard_delete: If True, permanently delete; if False, soft delete

        Returns:
            True if successful
        """
        try:
            # Get package
            package = self.db.get_package(package_name, version)
            if not package:
                raise R2NotFoundError(f"Package {package_name} v{version} not found")

            # No permission check - localhost only

            if hard_delete:
                # Delete from R2 storage
                self.r2_client.delete_file(package['r2_key'])

                # Hard delete from database
                self.db.delete_package(package['id'], soft_delete=False)
                logger.info(f"Hard deleted package {package_name} v{version}")
            else:
                # Soft delete (keep in storage, mark as deleted in DB)
                self.db.delete_package(package['id'], soft_delete=True)
                logger.info(f"Soft deleted package {package_name} v{version}")

            return True

        except R2NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete package: {e}")
            raise R2StorageError(f"Package deletion failed: {e}")

    def get_package_info(
        self,
        package_name: str,
        version: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get package information

        Args:
            package_name: Package name
            version: Package version

        Returns:
            Package information dict or None
        """
        try:
            return self.db.get_package(package_name, version)
        except Exception as e:
            logger.error(f"Failed to get package info: {e}")
            return None

    def list_package_versions(
        self,
        package_name: str,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        List all versions of a package

        Args:
            package_name: Package name
            limit: Results per page
            offset: Pagination offset

        Returns:
            Dict with versions list and pagination info
        """
        try:
            versions = self.db.list_package_versions(package_name, limit, offset)

            # Get total count (approximate)
            total = len(versions) if len(versions) < limit else limit + offset + 1

            return {
                'package_name': package_name,
                'versions': versions,
                'total': total,
                'limit': limit,
                'offset': offset
            }

        except Exception as e:
            logger.error(f"Failed to list package versions: {e}")
            return {
                'package_name': package_name,
                'versions': [],
                'total': 0,
                'limit': limit,
                'offset': offset
            }

    def search_packages(
        self,
        search_term: Optional[str] = None,
        tags: Optional[list[str]] = None,
        is_public: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Search packages

        Args:
            search_term: Search term
            tags: Filter by tags
            is_public: Filter by public status
            limit: Results per page
            offset: Pagination offset

        Returns:
            Dict with search results and pagination info
        """
        try:
            results = self.db.search_packages(
                search_term=search_term,
                tags=tags,
                is_public=is_public,
                limit=limit,
                offset=offset
            )

            total = len(results) if len(results) < limit else limit + offset + 1

            return {
                'results': results,
                'total': total,
                'limit': limit,
                'offset': offset
            }

        except Exception as e:
            logger.error(f"Failed to search packages: {e}")
            return {
                'results': [],
                'total': 0,
                'limit': limit,
                'offset': offset
            }

    def update_package_metadata(
        self,
        package_name: str,
        version: str,
        **updates
    ) -> Optional[Dict[str, Any]]:
        """
        Update package metadata

        **LOCALHOST ONLY** - No permission check required

        Args:
            package_name: Package name
            version: Package version
            **updates: Fields to update

        Returns:
            Updated package dict or None
        """
        try:
            # Get package
            package = self.db.get_package(package_name, version)
            if not package:
                raise R2NotFoundError(f"Package {package_name} v{version} not found")

            # Update database (no permission check - localhost only)
            updated = self.db.update_package(package['id'], **updates)

            logger.info(f"Updated package {package_name} v{version}")
            return updated

        except R2NotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to update package: {e}")
            return None

    def get_package_stats(
        self,
        package_name: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """
        Get package statistics

        Args:
            package_name: Optional specific package name

        Returns:
            List of package statistics
        """
        try:
            return self.db.get_package_stats(package_name)
        except Exception as e:
            logger.error(f"Failed to get package stats: {e}")
            return []

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get overall storage statistics

        Returns:
            Storage statistics dict
        """
        try:
            db_stats = self.db.get_storage_stats()

            # Get R2 bucket stats (optional, can be expensive)
            try:
                r2_stats = self.r2_client.get_bucket_size()
                db_stats['r2_bucket_size_bytes'] = r2_stats['total_size_bytes']
                db_stats['r2_object_count'] = r2_stats['object_count']
            except:
                pass

            db_stats['bucket_name'] = self.r2_client.bucket_name
            return db_stats

        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {}

    def cleanup_old_packages(
        self,
        days_threshold: int = 90,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        Clean up old archived packages

        Args:
            days_threshold: Archive age threshold in days
            dry_run: Preview only if True

        Returns:
            Cleanup result dict
        """
        try:
            packages = self.db.cleanup_old_packages(days_threshold, dry_run)

            if not dry_run:
                # Delete from R2 storage
                deleted_count = 0
                for pkg in packages:
                    try:
                        self.r2_client.delete_file(pkg['r2_key'])
                        deleted_count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete R2 file {pkg['r2_key']}: {e}")

                logger.info(f"Cleaned up {deleted_count} old packages")

            return {
                'packages_marked': len(packages),
                'dry_run': dry_run,
                'packages': packages
            }

        except Exception as e:
            logger.error(f"Failed to cleanup old packages: {e}")
            return {
                'packages_marked': 0,
                'dry_run': dry_run,
                'packages': []
            }

    def verify_package_integrity(
        self,
        package_name: str,
        version: str
    ) -> bool:
        """
        Verify package file integrity

        Args:
            package_name: Package name
            version: Package version

        Returns:
            True if integrity verified
        """
        try:
            package = self.db.get_package(package_name, version)
            if not package:
                return False

            return self.r2_client.verify_file_integrity(
                r2_key=package['r2_key'],
                expected_hash=package['file_hash']
            )

        except Exception as e:
            logger.error(f"Failed to verify package integrity: {e}")
            return False

    def _generate_r2_key(self, package_name: str, version: str) -> str:
        """
        Generate R2 storage key for package

        Format: packages/{package_name}/{version}/{package_name}
        This preserves the original file extension in the downloaded filename.

        Args:
            package_name: Package name (may include file extension like .tar.gz)
            version: Package version

        Returns:
            R2 storage key

        Examples:
            - package_name='my-app.tar.gz', version='1.0.0'
              → 'packages/my-app.tar.gz/1.0.0/my-app.tar.gz'
            - package_name='tool.zip', version='2.1.0'
              → 'packages/tool.zip/2.1.0/tool.zip'
        """
        # Format: packages/{package_name}/{version}/{package_name}
        # Removes version suffix from filename to preserve original extension
        safe_name = package_name.replace('/', '-')
        safe_version = version.replace('/', '-')
        return f"packages/{safe_name}/{safe_version}/{safe_name}"
