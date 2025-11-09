"""
Cloudflare R2 Storage Client

S3-compatible client wrapper for Cloudflare R2 storage operations.
"""

import os
import hashlib
from typing import Optional, Dict, Any, BinaryIO, Union
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError
    from botocore.config import Config
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    boto3 = None
    ClientError = None
    NoCredentialsError = None
    PartialCredentialsError = None
    Config = None

from .exceptions import (
    R2StorageError,
    R2ConnectionError,
    R2AuthenticationError,
    R2UploadError,
    R2DownloadError,
    R2DeleteError,
    R2NotFoundError,
    R2ConfigurationError
)


class R2Client:
    """
    Cloudflare R2 Storage Client

    Provides S3-compatible interface for R2 operations including upload,
    download, delete, and presigned URL generation.
    """

    def __init__(
        self,
        account_id: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        public_domain: Optional[str] = None
    ):
        """
        Initialize R2 client

        Args:
            account_id: Cloudflare account ID
            access_key_id: R2 access key ID
            secret_access_key: R2 secret access key
            bucket_name: R2 bucket name
            endpoint_url: R2 endpoint URL (optional, auto-generated if account_id provided)
            public_domain: Custom public domain for R2 bucket (optional)
        """
        if not BOTO3_AVAILABLE:
            raise R2ConfigurationError("boto3 is required for R2 client. Install with: uv add boto3")

        # Load from environment if not provided
        self.account_id = account_id or os.getenv('R2_ACCOUNT_ID')
        self.access_key_id = access_key_id or os.getenv('R2_ACCESS_KEY_ID')
        self.secret_access_key = secret_access_key or os.getenv('R2_SECRET_ACCESS_KEY')
        self.bucket_name = bucket_name or os.getenv('R2_BUCKET_NAME')
        logger.info(f"当前r2使用的bucket是{self.bucket_name}")
        self.public_domain = public_domain or os.getenv('R2_PUBLIC_DOMAIN')

        # Validate required credentials
        if not all([self.access_key_id, self.secret_access_key, self.bucket_name]):
            raise R2ConfigurationError(
                "R2 credentials incomplete. Required: R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME"
            )

        # Generate endpoint URL if not provided
        if endpoint_url:
            self.endpoint_url = endpoint_url
        elif self.account_id:
            self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
        else:
            self.endpoint_url = os.getenv('R2_ENDPOINT_URL')

        if not self.endpoint_url:
            raise R2ConfigurationError(
                "R2 endpoint URL not configured. Provide endpoint_url or R2_ACCOUNT_ID"
            )

        # Initialize S3 client with R2 configuration
        self._client = None
        self._initialize_client()

        logger.info(f"R2 client initialized for bucket: {self.bucket_name}")

    def _initialize_client(self):
        """Initialize boto3 S3 client with R2 configuration"""
        try:
            # Configure boto3 for R2 (S3-compatible)
            config = Config(
                signature_version='s3v4',
                s3={
                    'addressing_style': 'path'
                }
            )

            self._client = boto3.client(
                's3',
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                config=config,
                region_name='auto'  # R2 uses 'auto' as region
            )

        except (NoCredentialsError, PartialCredentialsError) as e:
            raise R2AuthenticationError(f"Invalid R2 credentials: {e}")
        except Exception as e:
            raise R2ConnectionError(f"Failed to initialize R2 client: {e}")

    @property
    def client(self):
        """Get boto3 S3 client instance"""
        if not self._client:
            self._initialize_client()
        return self._client

    def upload_file(
        self,
        file_path: Union[str, Path],
        r2_key: str,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload file to R2 storage

        Args:
            file_path: Local file path
            r2_key: R2 object key (path in bucket)
            metadata: Optional metadata dict
            content_type: Optional content type

        Returns:
            Dict with upload information (etag, size, hash)
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise R2UploadError(f"File not found: {file_path}")

            # Calculate file hash
            file_hash = self._calculate_file_hash(file_path)
            file_size = file_path.stat().st_size

            # Prepare upload parameters
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
            if content_type:
                extra_args['ContentType'] = content_type

            # Upload file
            self.client.upload_file(
                str(file_path),
                self.bucket_name,
                r2_key,
                ExtraArgs=extra_args if extra_args else None
            )

            logger.info(f"Uploaded file to R2: {r2_key} ({file_size} bytes)")

            return {
                'r2_key': r2_key,
                'file_size': file_size,
                'file_hash': file_hash,
                'hash_algorithm': 'sha256',
                'uploaded_at': datetime.utcnow().isoformat()
            }

        except ClientError as e:
            raise R2UploadError(f"Failed to upload file: {e}")
        except Exception as e:
            raise R2UploadError(f"Upload error: {e}")

    def upload_fileobj(
        self,
        file_obj: BinaryIO,
        r2_key: str,
        metadata: Optional[Dict[str, str]] = None,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload file object to R2 storage

        Args:
            file_obj: File-like object
            r2_key: R2 object key
            metadata: Optional metadata
            content_type: Optional content type

        Returns:
            Dict with upload information
        """
        try:
            # Read file content for hash calculation
            file_obj.seek(0)
            file_content = file_obj.read()
            file_size = len(file_content)
            file_hash = hashlib.sha256(file_content).hexdigest()

            # Reset file pointer
            file_obj.seek(0)

            # Prepare upload parameters
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
            if content_type:
                extra_args['ContentType'] = content_type

            # Upload file object
            self.client.upload_fileobj(
                file_obj,
                self.bucket_name,
                r2_key,
                ExtraArgs=extra_args if extra_args else None
            )

            logger.info(f"Uploaded file object to R2: {r2_key} ({file_size} bytes)")

            return {
                'r2_key': r2_key,
                'file_size': file_size,
                'file_hash': file_hash,
                'hash_algorithm': 'sha256',
                'uploaded_at': datetime.utcnow().isoformat()
            }

        except ClientError as e:
            raise R2UploadError(f"Failed to upload file object: {e}")
        except Exception as e:
            raise R2UploadError(f"Upload error: {e}")

    def download_file(self, r2_key: str, local_path: Union[str, Path]) -> Path:
        """
        Download file from R2 storage

        Args:
            r2_key: R2 object key
            local_path: Local destination path

        Returns:
            Path to downloaded file
        """
        try:
            local_path = Path(local_path)
            local_path.parent.mkdir(parents=True, exist_ok=True)

            self.client.download_file(
                self.bucket_name,
                r2_key,
                str(local_path)
            )

            logger.info(f"Downloaded file from R2: {r2_key} -> {local_path}")
            return local_path

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise R2NotFoundError(f"Object not found: {r2_key}")
            raise R2DownloadError(f"Failed to download file: {e}")
        except Exception as e:
            raise R2DownloadError(f"Download error: {e}")

    def delete_file(self, r2_key: str) -> bool:
        """
        Delete file from R2 storage

        Args:
            r2_key: R2 object key

        Returns:
            True if successful
        """
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=r2_key
            )

            logger.info(f"Deleted file from R2: {r2_key}")
            return True

        except ClientError as e:
            raise R2DeleteError(f"Failed to delete file: {e}")
        except Exception as e:
            raise R2DeleteError(f"Delete error: {e}")

    def file_exists(self, r2_key: str) -> bool:
        """
        Check if file exists in R2 storage

        Args:
            r2_key: R2 object key

        Returns:
            True if file exists
        """
        try:
            self.client.head_object(
                Bucket=self.bucket_name,
                Key=r2_key
            )
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise R2StorageError(f"Error checking file existence: {e}")

    def get_file_metadata(self, r2_key: str) -> Dict[str, Any]:
        """
        Get file metadata from R2 storage

        Args:
            r2_key: R2 object key

        Returns:
            Dict with file metadata
        """
        try:
            response = self.client.head_object(
                Bucket=self.bucket_name,
                Key=r2_key
            )

            return {
                'r2_key': r2_key,
                'size': response.get('ContentLength'),
                'content_type': response.get('ContentType'),
                'last_modified': response.get('LastModified'),
                'etag': response.get('ETag', '').strip('"'),
                'metadata': response.get('Metadata', {})
            }

        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                raise R2NotFoundError(f"Object not found: {r2_key}")
            raise R2StorageError(f"Failed to get metadata: {e}")

    def generate_presigned_url(
        self,
        r2_key: str,
        expiration: int = 3600,
        use_public_domain: bool = True
    ) -> str:
        """
        Generate presigned URL for file download

        Args:
            r2_key: R2 object key
            expiration: URL expiration time in seconds (default: 1 hour)
            use_public_domain: Use custom public domain if configured

        Returns:
            Presigned download URL
        """
        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': r2_key
                },
                ExpiresIn=expiration
            )

            # Replace endpoint with public domain if configured
            if use_public_domain and self.public_domain:
                url = url.replace(self.endpoint_url, self.public_domain.rstrip('/'))

            return url

        except ClientError as e:
            raise R2StorageError(f"Failed to generate presigned URL: {e}")

    def list_files(
        self,
        prefix: Optional[str] = None,
        max_keys: int = 1000
    ) -> list[Dict[str, Any]]:
        """
        List files in R2 bucket

        Args:
            prefix: Optional prefix filter
            max_keys: Maximum number of keys to return

        Returns:
            List of file information dicts
        """
        try:
            params = {
                'Bucket': self.bucket_name,
                'MaxKeys': max_keys
            }
            if prefix:
                params['Prefix'] = prefix

            response = self.client.list_objects_v2(**params)

            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj.get('ETag', '').strip('"')
                })

            return files

        except ClientError as e:
            raise R2StorageError(f"Failed to list files: {e}")

    def get_bucket_size(self) -> Dict[str, Any]:
        """
        Calculate total bucket size and object count

        Returns:
            Dict with size and count information
        """
        try:
            total_size = 0
            object_count = 0

            paginator = self.client.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=self.bucket_name):
                for obj in page.get('Contents', []):
                    total_size += obj['Size']
                    object_count += 1

            return {
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'object_count': object_count
            }

        except ClientError as e:
            raise R2StorageError(f"Failed to calculate bucket size: {e}")

    @staticmethod
    def _calculate_file_hash(file_path: Path, algorithm: str = 'sha256') -> str:
        """
        Calculate file hash

        Args:
            file_path: Path to file
            algorithm: Hash algorithm (default: sha256)

        Returns:
            Hex digest of file hash
        """
        hash_func = hashlib.new(algorithm)
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                hash_func.update(chunk)
        return hash_func.hexdigest()

    def verify_file_integrity(self, r2_key: str, expected_hash: str) -> bool:
        """
        Verify file integrity by comparing hash

        Args:
            r2_key: R2 object key
            expected_hash: Expected file hash

        Returns:
            True if hash matches
        """
        try:
            # Download file to temp location
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

            self.download_file(r2_key, tmp_path)
            actual_hash = self._calculate_file_hash(tmp_path)

            # Clean up temp file
            tmp_path.unlink()

            return actual_hash == expected_hash

        except Exception as e:
            logger.error(f"Failed to verify file integrity: {e}")
            return False
