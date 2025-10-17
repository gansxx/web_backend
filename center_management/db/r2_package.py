"""
R2 Package Database Operations

Database layer for R2 package management system.
Inherits from BaseConfig for Supabase client access.
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from loguru import logger
from .base_config import BaseConfig


class R2PackageConfig(BaseConfig):
    """
    R2 Package Database Operations

    Provides CRUD operations and queries for R2 package management.
    Uses Supabase PostgreSQL functions and RLS policies.
    """

    def __init__(self):
        """Initialize R2 package database operations"""
        super().__init__()

        # Get schema name from database using get_schema_name() function
        # This is primarily for logging and debugging purposes
        # All actual database operations are handled through RPC functions
        # which internally use get_schema_name() to route to the correct schema
        try:
            result = self.supabase.rpc('get_schema_name', {}).execute()
            self.schema_name = result.data if result.data else 'public'
        except Exception as e:
            logger.warning(f"Failed to get schema name from database: {e}, using 'public'")
            self.schema_name = 'public'

        logger.info(f"R2PackageConfig initialized successfully (schema: {self.schema_name})")

    def create_package(
        self,
        package_name: str,
        version: str,
        r2_key: str,
        file_size: int,
        file_hash: str,
        hash_algorithm: str,
        uploader_id: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create new package record

        Args:
            package_name: Package name
            version: Semantic version
            r2_key: R2 storage key
            file_size: File size in bytes
            file_hash: File hash
            hash_algorithm: Hash algorithm used
            uploader_id: User ID of uploader
            description: Optional description
            tags: Optional list of tags
            is_public: Whether package is public
            metadata: Optional metadata dict

        Returns:
            Created package record
        """
        try:
            import json

            response = self.supabase.rpc('create_r2_package', {
                'p_package_name': package_name,
                'p_version': version,
                'p_r2_key': r2_key,
                'p_file_size': file_size,
                'p_file_hash': file_hash,
                'p_hash_algorithm': hash_algorithm,
                'p_uploader_id': uploader_id,
                'p_description': description,
                'p_tags': tags or [],  # PostgreSQL JSONB handles JSON serialization automatically
                'p_is_public': is_public,
                'p_metadata': metadata or {}  # PostgreSQL JSONB handles JSON serialization automatically
            }).execute()

            if response.data:
                logger.info(f"Created package: {package_name} v{version}")
                return response.data[0]
            else:
                raise Exception("No data returned from function")

        except Exception as e:
            logger.error(f"Failed to create package {package_name} v{version}: {e}")
            raise

    def get_package_by_id(self, package_id: str) -> Optional[Dict[str, Any]]:
        """
        Get package by ID

        Args:
            package_id: Package UUID

        Returns:
            Package record or None
        """
        try:
            response = self.supabase.rpc('get_r2_package_by_id', {
                'p_package_id': package_id
            }).execute()

            return response.data[0] if response.data else None

        except Exception as e:
            logger.error(f"Failed to get package {package_id}: {e}")
            return None

    def get_package(
        self,
        package_name: str,
        version: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get package by name and version

        Args:
            package_name: Package name
            version: Package version

        Returns:
            Package record or None
        """
        try:
            response = self.supabase.rpc('get_r2_package', {
                'p_package_name': package_name,
                'p_version': version
            }).execute()

            return response.data[0] if response.data else None

        except Exception as e:
            logger.error(f"Failed to get package {package_name} v{version}: {e}")
            return None

    def list_package_versions(
        self,
        package_name: str,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List all versions of a package

        Args:
            package_name: Package name
            limit: Results per page
            offset: Pagination offset

        Returns:
            List of package versions
        """
        try:
            response = self.supabase.rpc(
                'get_r2_package_versions',
                {
                    'p_package_name': package_name,
                    'p_limit': limit,
                    'p_offset': offset
                }
            ).execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Failed to list versions for {package_name}: {e}")
            return []

    def search_packages(
        self,
        search_term: Optional[str] = None,
        tags: Optional[List[str]] = None,
        is_public: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Search packages by name, description, or tags

        Args:
            search_term: Search term
            tags: Filter by tags
            is_public: Filter by public status
            limit: Results per page
            offset: Pagination offset

        Returns:
            List of matching packages
        """
        try:
            response = self.supabase.rpc(
                'search_r2_packages',
                {
                    'p_search_term': search_term,
                    'p_tags': tags,
                    'p_is_public': is_public,
                    'p_limit': limit,
                    'p_offset': offset
                }
            ).execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Failed to search packages: {e}")
            return []

    def update_package(
        self,
        package_id: str,
        **updates
    ) -> Optional[Dict[str, Any]]:
        """
        Update package record

        Args:
            package_id: Package UUID
            **updates: Fields to update

        Returns:
            Updated package record or None
        """
        try:
            params = {'p_package_id': package_id}

            # Map update fields to function parameters
            if 'description' in updates:
                params['p_description'] = updates['description']
            if 'tags' in updates:
                params['p_tags'] = updates['tags']  # PostgreSQL JSONB handles JSON serialization automatically
            if 'is_public' in updates:
                params['p_is_public'] = updates['is_public']
            if 'status' in updates:
                params['p_status'] = updates['status']
            if 'metadata' in updates:
                params['p_metadata'] = updates['metadata']  # PostgreSQL JSONB handles JSON serialization automatically

            response = self.supabase.rpc('update_r2_package', params).execute()

            if response.data:
                logger.info(f"Updated package {package_id}")
                return response.data[0]
            return None

        except Exception as e:
            logger.error(f"Failed to update package {package_id}: {e}")
            return None

    def delete_package(
        self,
        package_id: str,
        soft_delete: bool = True
    ) -> bool:
        """
        Delete package (soft or hard delete)

        Args:
            package_id: Package UUID
            soft_delete: If True, mark as deleted; if False, remove from DB

        Returns:
            True if successful
        """
        try:
            response = self.supabase.rpc('delete_r2_package', {
                'p_package_id': package_id,
                'p_hard_delete': not soft_delete  # Function uses hard_delete flag
            }).execute()

            success = response.data if response.data else False
            if success:
                logger.info(f"Deleted package {package_id} (soft={soft_delete})")
            return success

        except Exception as e:
            logger.error(f"Failed to delete package {package_id}: {e}")
            return False

    def record_download(
        self,
        package_id: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        Record package download

        Args:
            package_id: Package UUID
            user_id: Optional user ID
            ip_address: Optional IP address
            user_agent: Optional user agent

        Returns:
            True if successful
        """
        try:
            self.supabase.rpc(
                'record_r2_package_download',
                {
                    'p_package_id': package_id,
                    'p_user_id': user_id,
                    'p_ip_address': ip_address,
                    'p_user_agent': user_agent
                }
            ).execute()

            return True

        except Exception as e:
            logger.error(f"Failed to record download for {package_id}: {e}")
            return False

    def get_package_stats(
        self,
        package_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get package statistics

        Args:
            package_name: Optional specific package name

        Returns:
            List of package statistics
        """
        try:
            response = self.supabase.rpc(
                'get_r2_package_stats',
                {'p_package_name': package_name}
            ).execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Failed to get package stats: {e}")
            return []

    def get_download_history(
        self,
        package_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get download history for a package

        Args:
            package_id: Package UUID
            limit: Results per page
            offset: Pagination offset

        Returns:
            List of download records
        """
        try:
            response = self.supabase.rpc('get_r2_download_history', {
                'p_package_id': package_id,
                'p_limit': limit,
                'p_offset': offset
            }).execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Failed to get download history for {package_id}: {e}")
            return []

    def cleanup_old_packages(
        self,
        days_threshold: int = 90,
        dry_run: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Clean up old archived packages

        Args:
            days_threshold: Archive age threshold in days
            dry_run: If True, only preview; if False, execute cleanup

        Returns:
            List of packages marked for deletion
        """
        try:
            if dry_run:
                # Preview mode: Use RPC function for schema-agnostic query
                # For now, call the cleanup function but note it will execute
                # In the future, we can add a separate preview RPC function
                logger.warning("Dry run mode: Calling cleanup RPC (will execute, not preview)")
                response = self.supabase.rpc(
                    'cleanup_old_r2_packages',
                    {'p_days_threshold': days_threshold}
                ).execute()

                return response.data if response.data else []
            else:
                # Execute cleanup
                response = self.supabase.rpc(
                    'cleanup_old_r2_packages',
                    {'p_days_threshold': days_threshold}
                ).execute()

                return response.data if response.data else []

        except Exception as e:
            logger.error(f"Failed to cleanup old packages: {e}")
            return []

    def list_user_packages(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List packages uploaded by specific user

        Args:
            user_id: User UUID
            limit: Results per page
            offset: Pagination offset

        Returns:
            List of user's packages
        """
        try:
            response = self.supabase.rpc('list_user_r2_packages', {
                'p_user_id': user_id,
                'p_limit': limit,
                'p_offset': offset
            }).execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Failed to list user packages for {user_id}: {e}")
            return []

    def list_public_packages(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List public packages

        Args:
            limit: Results per page
            offset: Pagination offset

        Returns:
            List of public packages
        """
        try:
            response = self.supabase.rpc('list_public_r2_packages', {
                'p_limit': limit,
                'p_offset': offset
            }).execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Failed to list public packages: {e}")
            return []

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get overall storage statistics

        Returns:
            Dict with total counts and sizes
        """
        try:
            # Get all package stats using RPC function (schema-agnostic)
            stats = self.get_package_stats()

            # Calculate totals from package stats
            total_packages = len(stats)
            total_versions = sum(s.get('total_versions', 0) for s in stats)
            total_downloads = sum(s.get('total_downloads', 0) for s in stats)
            total_size_bytes = sum(s.get('total_size_bytes', 0) for s in stats)

            return {
                'total_packages': total_packages,
                'total_versions': total_versions,
                'total_downloads': total_downloads,
                'total_size_bytes': total_size_bytes,
                'total_size_mb': round(total_size_bytes / (1024 * 1024), 2),
                'total_size_gb': round(total_size_bytes / (1024 * 1024 * 1024), 2)
            }

        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {
                'total_packages': 0,
                'total_versions': 0,
                'total_downloads': 0,
                'total_size_bytes': 0,
                'total_size_mb': 0.0,
                'total_size_gb': 0.0
            }

    def check_package_exists(
        self,
        package_name: str,
        version: str
    ) -> bool:
        """
        Check if package version exists

        Args:
            package_name: Package name
            version: Package version

        Returns:
            True if exists
        """
        try:
            response = self.supabase.rpc('check_r2_package_exists', {
                'p_package_name': package_name,
                'p_version': version
            }).execute()

            return response.data if response.data else False

        except Exception as e:
            logger.error(f"Failed to check package existence: {e}")
            return False
