# R2 Package Management System

Complete software package distribution and storage management system using Cloudflare R2.

## Overview

This module provides a production-ready solution for managing software package distribution with version control, access management, and comprehensive statistics tracking.

### Key Features

- **Multi-Version Management**: Semantic versioning support with version history
- **Access Control**: Public/private packages with user-based permissions
- **File Integrity**: SHA-256 hash validation for download verification
- **Download Distribution**: Presigned URLs with configurable expiration
- **Statistics Tracking**: Download counts, storage usage, and package analytics
- **Automatic Cleanup**: Scheduled cleanup of old archived versions
- **Search & Discovery**: Full-text search with tag filtering
- **CDN Integration**: Optional custom domain support for CDN acceleration

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   API Layer                      │
│            (routes/r2_packages.py)              │
│                                                  │
│  ┌────────────────────────────────────────┐    │
│  │  External Access (Public Internet)     │    │
│  │  • Download endpoint only              │    │
│  │    - Public packages: No auth          │    │
│  │    - Private packages: Auth required   │    │
│  └────────────────────────────────────────┘    │
│                                                  │
│  ┌────────────────────────────────────────┐    │
│  │  Localhost-Only Access (127.0.0.1)     │    │
│  │  • All management endpoints            │    │
│  │    - Upload, Update, Delete, Search    │    │
│  │    - Statistics, Health, Cleanup       │    │
│  │    - No authentication required        │    │
│  └────────────────────────────────────────┘    │
└────────────────┬────────────────────────────────┘
                 │
┌────────────────▼────────────────────────────────┐
│              Package Manager                     │
│        (package_manager.py)                     │
│  - Upload/Download coordination                 │
│  - Version management                           │
│  - NO permission validation (localhost trust)   │
└────────┬───────────────────────┬────────────────┘
         │                       │
┌────────▼────────┐    ┌────────▼────────────────┐
│   R2 Client     │    │  Database Operations    │
│  (client.py)    │    │  (db/r2_package.py)    │
│  - S3 API       │    │  - PostgreSQL CRUD      │
│  - Upload/Down  │    │  - Statistics           │
│  - Presigned    │    │  - Search               │
└─────────────────┘    └─────────────────────────┘
         │                       │
┌────────▼────────┐    ┌────────▼────────────────┐
│ Cloudflare R2   │    │  Supabase PostgreSQL   │
│  (File Storage) │    │  (Metadata & Stats)    │
└─────────────────┘    └─────────────────────────┘
```

## Installation

### 1. Database Migration

**IMPORTANT**: Run migrations in the correct order!

```bash
source .env

# Step 1: Initialize schema configuration (REQUIRED FIRST)
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -v ON_ERROR_STOP=1 \
  -f center_management/db/migration/sql_schema_migration/00_schema_init.sql

# Step 2: Create R2 package system tables (uses dynamic schema)
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -v ON_ERROR_STOP=1 \
  -f center_management/db/migration/sql_schema_migration/r2_package_system.sql
```

**Schema Configuration**:
- Tables are created in the configured schema (set by `00_schema_init.sql`)
- Default schema is `tests` for testing environment
- Production can use `public` or custom schema
- The system automatically detects and uses the configured schema

### 2. Environment Configuration

Add R2 configuration to your `.env` file:

```env
# ==========================================
# Cloudflare R2 Configuration
# ==========================================

# Account & Credentials (Required)
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key

# Bucket Configuration (Required)
R2_BUCKET_NAME=test  # Or 'software-packages' for production

# Optional: Custom Domain for CDN
# R2_PUBLIC_DOMAIN=https://packages.yourdomain.com

# Package Management Limits (Optional - defaults shown)
R2_MAX_PACKAGE_SIZE_MB=500
R2_DOWNLOAD_URL_EXPIRY_SECONDS=3600  # 1 hour
```

**Current Configuration** (as of 2025-10-16):
- **Bucket**: `test` (development/testing)
- **Max Package Size**: 500 MB
- **Download URL Expiry**: 3600 seconds (1 hour)
- **Schema**: `tests` (isolated testing environment)
- **System Uploader**: `00000000-0000-0000-0000-000000000000` (system@localhost)

### 3. Application Integration

Add to `main.py`:

```python
from center_management.r2_storage import PackageManager

# Initialize package manager
try:
    package_manager = PackageManager()
    app.state.package_manager = package_manager
    logger.info("Package manager initialized")
except Exception as e:
    logger.error(f"Failed to initialize package manager: {e}")
    app.state.package_manager = None

# Register R2 routes
try:
    from routes.r2_packages import router as r2_packages_router
    app.include_router(r2_packages_router)
    logger.info("routes.r2_packages registered")
except Exception as e:
    logger.error(f"Failed to register routes.r2_packages: {e}")
```

## API Endpoints

### Package Upload

**POST /r2/packages/upload**

⚠️ **LOCALHOST ONLY**: This endpoint is restricted to localhost access for security. It cannot be accessed by authenticated users from external clients.

**Security Model**:
- Only accessible from `localhost`, `127.0.0.1`, or `::1` (IPv6 localhost)
- Designed for automated build/deployment systems running on the same machine
- External clients will receive `403 Forbidden` error
- Replaces user authentication with IP-based access control

```bash
# Only works when executed on the server itself
curl -X POST http://localhost:8001/r2/packages/upload \
  -F "file=@my-package-1.0.0.tar.gz" \
  -F "package_name=my-package" \
  -F "version=1.0.0" \
  -F "description=My awesome package" \
  -F "tags=python,cli,utility" \
  -F "is_public=true" \
  -F "uploader_id=optional-user-uuid"
```

**Parameters**:
- `file` (required): Package file to upload
- `package_name` (required): Package name (alphanumeric with dashes)
- `version` (required): Semantic version (e.g., 1.0.0)
- `description` (optional): Package description
- `tags` (optional): Comma-separated tags
- `is_public` (optional): Public access flag (default: false)
- `uploader_id` (optional): User UUID (defaults to system ID if not provided)

Response:
```json
{
  "id": "uuid",
  "package_name": "my-package",
  "version": "1.0.0",
  "r2_key": "packages/my-package/1.0.0/my-package-1.0.0",
  "file_size": 1048576,
  "file_hash": "sha256hash...",
  "hash_algorithm": "sha256",
  "created_at": "2025-10-15T10:00:00Z"
}
```

### Package Download

**GET /r2/packages/{package_name}/{version}/download**

Generate presigned download URL. Accessible to authenticated users.

**Access Control**:
- Public packages: Accessible without authentication
- Private packages: Requires authentication and ownership verification
- Returns presigned URL valid for specified duration

```bash
# Public package (no authentication required)
curl http://localhost:8001/r2/packages/my-package/1.0.0/download?expiration=3600

# Private package (requires authentication)
curl http://localhost:8001/r2/packages/my-package/1.0.0/download?expiration=3600 \
  -H "Cookie: access_token=YOUR_TOKEN"
```

Response:
```json
{
  "package_name": "my-package",
  "version": "1.0.0",
  "download_url": "https://...",
  "expires_in": 3600,
  "file_size": 1048576,
  "file_hash": "sha256hash..."
}
```

### Package Information

**GET /r2/packages/{package_name}/{version}**

⚠️ **LOCALHOST ONLY**: This endpoint is only accessible from localhost (127.0.0.1, ::1).

Get detailed package metadata.

```bash
# Only works when executed on the server itself
curl http://localhost:8001/r2/packages/my-package/1.0.0
```

### List Package Versions

**GET /r2/packages/{package_name}/versions**

⚠️ **LOCALHOST ONLY**: This endpoint is only accessible from localhost (127.0.0.1, ::1).

List all versions of a package.

```bash
# Only works when executed on the server itself
curl http://localhost:8001/r2/packages/my-package/versions?limit=20&offset=0
```

### Search Packages

**POST /r2/packages/search**

⚠️ **LOCALHOST ONLY**: This endpoint is only accessible from localhost (127.0.0.1, ::1).

Search packages by name, description, or tags.

```bash
# Only works when executed on the server itself
curl -X POST http://localhost:8001/r2/packages/search \
  -H "Content-Type: application/json" \
  -d '{
    "search_term": "cli",
    "tags": ["python"],
    "limit": 50,
    "offset": 0
  }'
```

### List Public Packages

**GET /r2/packages/public**

⚠️ **LOCALHOST ONLY**: This endpoint is only accessible from localhost (127.0.0.1, ::1).

List all publicly accessible packages.

```bash
# Only works when executed on the server itself
curl http://localhost:8001/r2/packages/public?limit=50&offset=0
```

### My Uploads

**GET /r2/packages/my-uploads**

⚠️ **LOCALHOST ONLY**: This endpoint is only accessible from localhost (127.0.0.1, ::1).

List packages uploaded by specific user. Requires `user_id` query parameter.

```bash
# Only works when executed on the server itself
curl "http://localhost:8001/r2/packages/my-uploads?user_id=USER_UUID&limit=50&offset=0"
```

### Update Package

**PATCH /r2/packages/{package_name}/{version}**

⚠️ **LOCALHOST ONLY**: This endpoint is only accessible from localhost (127.0.0.1, ::1). No authentication required.

Update package metadata.

```bash
# Only works when executed on the server itself
curl -X PATCH http://localhost:8001/r2/packages/my-package/1.0.0 \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated description",
    "tags": ["python", "cli", "tool"],
    "is_public": true
  }'
```

### Delete Package

**DELETE /r2/packages/{package_name}/{version}**

⚠️ **LOCALHOST ONLY**: This endpoint is only accessible from localhost (127.0.0.1, ::1). No authentication required.

Delete package (soft delete by default).

```bash
# Soft delete (mark as deleted) - only works when executed on the server itself
curl -X DELETE http://localhost:8001/r2/packages/my-package/1.0.0

# Hard delete (permanently remove) - only works when executed on the server itself
curl -X DELETE "http://localhost:8001/r2/packages/my-package/1.0.0?hard_delete=true"
```

### Package Statistics

**GET /r2/packages/stats/{package_name}**

⚠️ **LOCALHOST ONLY**: This endpoint is only accessible from localhost (127.0.0.1, ::1).

Get statistics for specific package.

```bash
# Only works when executed on the server itself
curl http://localhost:8001/r2/packages/stats/my-package
```

Response:
```json
{
  "package_name": "my-package",
  "total_versions": 5,
  "total_downloads": 1250,
  "total_size_bytes": 5242880,
  "total_size_mb": 5.0,
  "latest_version": "1.0.4",
  "latest_upload_date": "2025-10-15T10:00:00Z"
}
```

### Storage Statistics

**GET /r2/packages/stats/storage**

⚠️ **LOCALHOST ONLY**: This endpoint is only accessible from localhost (127.0.0.1, ::1).

Get overall storage statistics.

```bash
# Only works when executed on the server itself
curl http://localhost:8001/r2/packages/stats/storage
```

Response:
```json
{
  "total_packages": 150,
  "total_versions": 500,
  "total_downloads": 50000,
  "total_size_bytes": 10737418240,
  "total_size_mb": 10240.0,
  "total_size_gb": 10.0,
  "bucket_name": "software-packages"
}
```

### Cleanup Old Packages

**POST /r2/packages/cleanup**

⚠️ **LOCALHOST ONLY**: This endpoint is only accessible from localhost (127.0.0.1, ::1). No authentication required.

Clean up old archived packages.

```bash
# Dry run (preview only) - only works when executed on the server itself
curl -X POST http://localhost:8001/r2/packages/cleanup \
  -H "Content-Type: application/json" \
  -d '{
    "days_threshold": 90,
    "dry_run": true
  }'

# Execute cleanup - only works when executed on the server itself
curl -X POST http://localhost:8001/r2/packages/cleanup \
  -H "Content-Type: application/json" \
  -d '{
    "days_threshold": 90,
    "dry_run": false
  }'
```

### Verify Package Integrity

**GET /r2/packages/{package_name}/{version}/verify**

⚠️ **LOCALHOST ONLY**: This endpoint is only accessible from localhost (127.0.0.1, ::1).

Verify package file integrity.

```bash
# Only works when executed on the server itself
curl http://localhost:8001/r2/packages/my-package/1.0.0/verify
```

### Health Check

**GET /r2/packages/health**

⚠️ **LOCALHOST ONLY**: This endpoint is only accessible from localhost (127.0.0.1, ::1).

Check R2 and database connectivity.

```bash
# Only works when executed on the server itself
curl http://localhost:8001/r2/packages/health
```

## Python Client Usage

### Basic Upload

**Note**: Direct Python upload via PackageManager works because it bypasses the API endpoint and writes directly to R2 + database. The API endpoint restriction only applies to HTTP requests.

```python
from center_management.r2_storage import PackageManager
from pathlib import Path

pm = PackageManager()

# Upload package directly (bypasses API, no localhost restriction)
result = pm.upload_package(
    package_name="my-tool",
    version="1.0.0",
    file_obj=Path("./my-tool-1.0.0.tar.gz"),
    uploader_id=user_id,  # Or use system ID: "00000000-0000-0000-0000-000000000000"
    description="Command-line utility",
    tags=["cli", "python"],
    is_public=True
)

print(f"Uploaded: {result['package_name']} v{result['version']}")
print(f"Hash: {result['file_hash']}")
```

### Upload via API (Localhost Only)

```python
import requests

# This only works when executed on the server itself
response = requests.post(
    "http://localhost:8001/r2/packages/upload",
    files={"file": open("my-tool-1.0.0.tar.gz", "rb")},
    data={
        "package_name": "my-tool",
        "version": "1.0.0",
        "description": "Command-line utility",
        "tags": "cli,python",
        "is_public": "true"
    }
)

if response.status_code == 200:
    result = response.json()
    print(f"Uploaded: {result['package_name']} v{result['version']}")
elif response.status_code == 403:
    print("Error: Upload API only accessible from localhost")
else:
    print(f"Error: {response.json()['detail']}")
```

### Generate Download URL

```python
# Generate download URL
download_info = pm.download_package(
    package_name="my-tool",
    version="1.0.0",
    expiration=7200,  # 2 hours
    user_id=user_id,
    ip_address="192.168.1.1"
)

print(f"Download URL: {download_info['download_url']}")
print(f"Expires in: {download_info['expires_in']} seconds")
```

### Search Packages

```python
# Search for packages
results = pm.search_packages(
    search_term="cli",
    tags=["python"],
    limit=20
)

for pkg in results['results']:
    print(f"{pkg['package_name']} v{pkg['version']} - {pkg['download_count']} downloads")
```

### Get Statistics

```python
# Package statistics
stats = pm.get_package_stats("my-tool")
print(f"Total downloads: {stats[0]['total_downloads']}")

# Storage statistics
storage = pm.get_storage_stats()
print(f"Total packages: {storage['total_packages']}")
print(f"Storage used: {storage['total_size_gb']} GB")
```

## Database Schema

**Schema Organization**:
- Tables are created in the configured schema (default: `tests`)
- Configured via `get_schema_name()` function in `00_schema_init.sql`
- Python application automatically discovers and uses the correct schema
- Production deployments can use `public` or custom schema names

### r2_packages Table

**Table Name**: `{schema}.r2_packages` (e.g., `tests.r2_packages`)

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| package_name | TEXT | Package name |
| version | TEXT | Semantic version |
| r2_key | TEXT | R2 storage key (unique) |
| file_size | BIGINT | File size in bytes |
| file_hash | TEXT | SHA-256 hash |
| hash_algorithm | TEXT | Hash algorithm (default: sha256) |
| description | TEXT | Package description |
| tags | JSONB | Tags array |
| is_public | BOOLEAN | Public access flag |
| uploader_id | UUID | User ID (foreign key to auth.users) |
| download_count | INTEGER | Download counter |
| status | TEXT | active/archived/deleted |
| metadata | JSONB | Additional metadata |
| created_at | TIMESTAMPTZ | Creation timestamp |
| updated_at | TIMESTAMPTZ | Update timestamp |

**Constraints**:
- Version must follow semantic versioning pattern
- Unique constraint on (package_name, version)
- Foreign key to auth.users(id) with CASCADE delete

### r2_package_downloads Table

**Table Name**: `{schema}.r2_package_downloads` (e.g., `tests.r2_package_downloads`)

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| package_id | UUID | Package ID (foreign key) |
| user_id | UUID | User ID (nullable) |
| ip_address | INET | IP address |
| user_agent | TEXT | User agent string |
| downloaded_at | TIMESTAMPTZ | Download timestamp |

**Indexes**:
- Index on package_id for fast download history queries
- Index on downloaded_at for time-based analytics

## Database Functions

### Core Package Management (Schema-Agnostic RPC Functions)

**CRUD Operations**:
- `create_r2_package(...)` - Create new package record with file metadata
- `get_r2_package_by_id(package_id)` - Retrieve package by UUID
- `get_r2_package(package_name, version)` - Retrieve active package by name and version
- `update_r2_package(package_id, ...)` - Update package metadata (description, tags, visibility, status)
- `delete_r2_package(package_id, hard_delete)` - Soft delete (mark as deleted) or hard delete (permanent removal)

**Query Operations**:
- `list_user_r2_packages(user_id, limit, offset)` - List packages uploaded by specific user
- `list_public_r2_packages(limit, offset)` - List all public packages
- `check_r2_package_exists(package_name, version)` - Check if package version exists
- `get_r2_download_history(package_id, limit, offset)` - Get download history for a package

### Statistics & Analytics

- `record_r2_package_download(package_id, user_id, ip, user_agent)` - Record download and increment counter
- `get_r2_package_stats(package_name)` - Get aggregated package statistics (downloads, versions, size)
- `get_r2_package_versions(package_name, limit, offset)` - List all versions of a package

### Maintenance Operations

- `cleanup_old_r2_packages(days_threshold)` - Mark old archived packages for deletion
- `search_r2_packages(search_term, tags, is_public, limit, offset)` - Full-text search across packages

### Schema Management

- `get_schema_name()` - Returns configured schema name (`tests` or `public`)
- `update_r2_package_updated_at()` - Trigger function to auto-update `updated_at` timestamp

**Function Permissions**:
- `service_role` - Full access to all functions (for system operations)
- `authenticated` - Read access to query functions, restricted write access
- `anon` - Read access to public package listing only

## Security

### Access Control Model

**🌐 EXTERNAL ACCESS - Download Endpoint ONLY** (GET /r2/packages/{package_name}/{version}/download):
- **Public Packages**: Accessible from anywhere without authentication
- **Private Packages**: Require authentication (access_token cookie or Authorization header)
- **Purpose**: Allow users to download packages from anywhere
- **Download Tracking**: Records user_id, IP address, and user agent

**🔒 LOCALHOST ONLY - All Management Endpoints**:
- **Upload** (POST /r2/packages/upload)
- **Update** (PATCH /r2/packages/{package_name}/{version})
- **Delete** (DELETE /r2/packages/{package_name}/{version})
- **Search** (POST /r2/packages/search)
- **List Public** (GET /r2/packages/public)
- **My Uploads** (GET /r2/packages/my-uploads)
- **Package Info** (GET /r2/packages/{package_name}/{version})
- **List Versions** (GET /r2/packages/{package_name}/versions)
- **Statistics** (GET /r2/packages/stats/*)
- **Cleanup** (POST /r2/packages/cleanup)
- **Verify** (GET /r2/packages/{package_name}/{version}/verify)
- **Health** (GET /r2/packages/health)

**Localhost Endpoints Characteristics**:
- **Restricted IPs**: Only `localhost`, `127.0.0.1`, or `::1` (IPv6 localhost)
- **No Authentication Required**: IP-based trust model
- **Purpose**: Package management operations for administrators and automated systems
- **Returns 403 Forbidden**: When accessed from non-localhost IP

### Row Level Security (RLS)

**r2_packages Table**:
- Public packages: Readable by everyone (when status = 'active')
- Private packages: Readable only by uploader
- Insert: Authenticated users only
- Update/Delete: Only by package uploader
- Service role: Full access for system operations

**r2_package_downloads Table**:
- Download history: Only visible to package uploader
- Service role: Full access for analytics

### Authentication Methods

For endpoints requiring authentication:
- **Cookie-based**: `access_token` cookie
- **Header-based**: `Authorization: Bearer TOKEN`
- **Service role**: For system operations (not for regular users)

## Performance Optimization

### Indexes

- Composite index: `(package_name, version)`
- GIN index: `tags` (JSONB)
- Covering indexes for common queries
- Time-based index: `created_at DESC`

### Caching Strategy

- Database connection pooling via Supabase
- R2 presigned URL caching (application level)
- CDN integration for public packages

## Monitoring

### Key Metrics

- Total storage usage
- Download counts per package
- Upload success/failure rates
- Average download latency
- R2 API call volumes

### Health Checks

```bash
# Application health
curl http://localhost:8001/r2/packages/health

# Database connectivity
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" -c "SELECT COUNT(*) FROM r2_packages;"

# R2 connectivity (via Python)
python -c "from center_management.r2_storage import R2Client; R2Client().list_files(max_keys=1)"
```

## Troubleshooting

### Upload Failures

**Error: 403 Forbidden - "Upload API is only accessible from localhost"**
```
Cause: Request came from external IP, not localhost
Solution: Upload must be executed on the server itself (localhost)
- Use SSH to connect to server and run upload command locally
- Set up automated build/deployment pipeline on the server
- Cannot upload from external clients (by design for security)
```

**Error: Package already exists**
```
Solution: Use a different version number or delete the existing version
```

**Error: File size exceeds maximum**
```
Solution: Increase R2_MAX_PACKAGE_SIZE_MB or compress the package
```

**Error: R2 authentication failed**
```
Solution: Verify R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY in .env file
```

**Error: Package upload failed - JSON could not be generated (404)**
```
Cause: Database schema mismatch or missing tables
Solution:
1. Run 00_schema_init.sql migration first
2. Run r2_package_system.sql migration
3. Verify tables exist: psql -c "\dt {schema}.r2_*"
4. Check R2PackageConfig logs for schema detection
```

**Error: Could not find the function public.create_r2_package**
```
Cause: PostgREST schema cache not refreshed after creating new functions
Solution:
# Restart PostgREST container to refresh schema cache
docker restart supabase-rest

# Wait for PostgREST to be ready
sleep 3 && curl -s http://localhost:8000 > /dev/null && echo "PostgREST ready"

# Then retry your upload
```

**Error: Insert violates foreign key constraint "r2_packages_uploader_id_fkey"**
```
Cause: System uploader UUID (00000000-0000-0000-0000-000000000000) not in auth.users table
Solution:
# Create system user in auth.users table
PGPASSWORD="your-super-secret-and-long-postgres-password" \
psql "postgresql://postgres@localhost:5438/postgres" <<'EOF'
INSERT INTO auth.users (
  id, instance_id, aud, role, email,
  encrypted_password, email_confirmed_at,
  created_at, updated_at
) VALUES (
  '00000000-0000-0000-0000-000000000000'::uuid,
  '00000000-0000-0000-0000-000000000000'::uuid,
  'authenticated', 'authenticated', 'system@localhost',
  'SYSTEM-NO-PASSWORD', NOW(), NOW(), NOW()
) ON CONFLICT (id) DO NOTHING;
EOF
```

**Error: New row violates check constraint "r2_packages_version_check"**
```
Cause: Version string doesn't match semantic versioning pattern or regex was improperly escaped
Solution:
# Drop and recreate the version constraint with correct regex
ALTER TABLE tests.r2_packages DROP CONSTRAINT r2_packages_version_check;
ALTER TABLE tests.r2_packages ADD CONSTRAINT r2_packages_version_check
  CHECK (version ~ '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$');

# Valid version formats:
# 1.0.0 ✓
# 2.1.3-beta ✓
# 1.0.0+build.123 ✓
# 1.0 ✗ (missing patch version)
```

### Download Issues

**Error: Package not found**
```
Solution: Verify package name and version, check status is 'active'
```

**Error: Access denied**
```
Solution: Authenticate for private packages or request public access
```

### Database Errors

**Error: Package manager not initialized**
```
Solution: Check environment variables and database connection
```

**Error: RLS policy violation**
```
Solution: Verify user authentication and ownership
```

## RPC Function Architecture

### Why PostgreSQL Functions?

The R2 Package Management System uses PostgreSQL RPC (Remote Procedure Call) functions exclusively for all database operations instead of direct table access. This architecture provides several key advantages:

**1. Schema Abstraction**:
```python
# Python code doesn't need to know which schema tables are in
result = db.create_package(...)  # Works with any configured schema

# Function internally routes to correct schema
CREATE FUNCTION create_r2_package(...) AS $$
DECLARE
    app_schema TEXT := get_schema_name();  -- Dynamic schema resolution
BEGIN
    EXECUTE format('INSERT INTO %I.r2_packages ...', app_schema);
END;
$$
```

**2. PostgREST Independence**:
- RPC functions can be called regardless of PostgREST's `PGRST_DB_SCHEMAS` configuration
- No need to expose test/custom schemas publicly
- Better security through schema isolation

**3. Type Safety & Column Ordering**:
```sql
-- Explicit column ordering prevents type mismatches
RETURNING id, package_name, version, r2_key, file_size, file_hash, hash_algorithm,
          uploader_id, description, tags, is_public, download_count, status, metadata,
          created_at, updated_at
-- vs SELECT * which can return columns in different order
```

**4. Centralized Business Logic**:
- Version validation, constraint checks, and triggers all in database
- Consistent behavior across different client applications
- Easier to maintain and audit

**5. Security Through SECURITY DEFINER**:
```sql
CREATE FUNCTION create_r2_package(...)
SECURITY DEFINER  -- Function runs with creator's privileges
AS $$
-- Function can access tables even if caller doesn't have direct permission
-- RLS policies still apply to ensure data security
$$
```

### Using RPC Functions

**From Python (via Supabase client)**:
```python
from center_management.db.r2_package import R2PackageConfig

db = R2PackageConfig()

# Create package (calls create_r2_package RPC function)
result = db.create_package(
    package_name="my-tool",
    version="1.0.0",
    r2_key="packages/my-tool/1.0.0/my-tool-1.0.0",
    file_size=1048576,
    file_hash="sha256hash...",
    hash_algorithm="sha256",
    uploader_id="uuid-here",
    description="My awesome tool",
    tags=["cli", "python"],
    is_public=True
)
# Returns: Dict with all package fields
```

**Directly via psql**:
```bash
# Call RPC function directly
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" <<'EOF'
SELECT * FROM create_r2_package(
  'test-package',           -- package_name
  '1.0.0',                  -- version
  'packages/test/1.0.0/test-1.0.0',  -- r2_key
  1000,                     -- file_size
  'hash123',                -- file_hash
  'sha256',                 -- hash_algorithm
  '00000000-0000-0000-0000-000000000000'::uuid,  -- uploader_id
  'Test description',       -- description
  '["test"]'::jsonb,       -- tags
  true,                     -- is_public
  '{}'::jsonb              -- metadata
);
EOF
```

**Via PostgREST API**:
```bash
# Call via Supabase REST API
curl -X POST http://localhost:8000/rest/v1/rpc/create_r2_package \
  -H "apikey: $SERVICE_ROLE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "p_package_name": "test",
    "p_version": "1.0.0",
    "p_r2_key": "packages/test/1.0.0/test-1.0.0",
    "p_file_size": 1000,
    "p_file_hash": "hash123",
    "p_hash_algorithm": "sha256",
    "p_uploader_id": "00000000-0000-0000-0000-000000000000",
    "p_description": "Test",
    "p_tags": ["test"],
    "p_is_public": true,
    "p_metadata": {}
  }'
```

### Function Naming Convention

All R2 package management functions follow consistent naming:
- Prefix: No schema prefix required (schema-agnostic)
- CRUD: `create_`, `get_`, `update_`, `delete_`, `list_`, `check_`
- Entity: `r2_package` or `r2_download`
- Example: `create_r2_package`, `list_user_r2_packages`, `get_r2_download_history`

## Best Practices

### Version Management

- Use semantic versioning: `MAJOR.MINOR.PATCH`
- Document breaking changes in description
- Archive old versions instead of deleting
- Tag versions appropriately for discoverability

### Access Control

- **Network-Level Security**:
  - **CRITICAL**: Only the download endpoint is externally accessible
  - All management endpoints (upload, update, delete, etc.) are localhost-only
  - Use firewall rules or reverse proxy to enforce network isolation
  - Never expose management endpoints to public internet

- **Upload Security**:
  - Upload API is localhost-only by design
  - Set up automated deployment pipelines on server
  - Use SSH tunneling if needed for remote access
  - No user authentication required (IP-based trust)

- **Package Visibility**:
  - Default to private packages (requires authentication to download)
  - Make packages public only when necessary
  - Regularly audit public packages
  - Use custom domains for professional distribution

### Storage Optimization

- Enable automatic cleanup for old versions
- Archive infrequently downloaded packages
- Compress packages before upload
- Monitor storage costs

### Security

- **Infrastructure**:
  - Rotate R2 access keys periodically
  - Keep upload endpoint localhost-only
  - Use firewall rules to protect backend API

- **Application**:
  - Use short expiration times for download URLs (default: 1 hour)
  - Enable webhook notifications for uploads
  - Audit download logs regularly
  - Implement rate limiting for download endpoints

- **Database**:
  - Use separate schemas for test/production environments
  - Enable RLS policies for all package tables
  - Regular backup of package metadata

## Architecture Changes

### Recent Updates (2025-10-16)

**1. Localhost-Only Access Control (Security Enhancement)**:
- **Complete API Lockdown**: All management endpoints restricted to localhost access only
- **Single External Endpoint**: Only the download endpoint (`GET /{package_name}/{version}/download`) is externally accessible
- **Authentication Removal**: Removed authentication requirements from localhost-only endpoints
  - No more `access_token` validation for management operations
  - Simplified API surface by moving security to network layer
- **PackageManager Refactoring**: Removed `user_id` permission checks from `update_package_metadata()` and `delete_package()`
- **Benefits**:
  - Enhanced security: Management operations only from trusted network
  - Simplified code: Removed complex authentication/authorization logic
  - Better performance: No token validation overhead for internal operations
  - Clear separation: External users can only download, internal systems can manage
- **12 Localhost-Only Endpoints**:
  - Upload, Update, Delete, Search, List (public/versions/user), Package Info
  - Statistics (package/storage), Cleanup, Verify, Health
- **Migration Impact**: Existing external API clients can no longer manage packages - must use SSH or internal systems

**2. Schema-Agnostic PostgreSQL Functions (RPC-Based Architecture)**:
- **Complete Refactoring**: All database operations now use PostgreSQL RPC functions instead of direct table access
- **Schema Abstraction**: Functions internally use `get_schema_name()` to route operations to the correct schema
- **PostgREST Independence**: No need to expose `tests` or custom schemas through `PGRST_DB_SCHEMAS`
- **9 New CRUD Functions**:
  - `create_r2_package()` - Insert new packages with proper column ordering
  - `get_r2_package_by_id()` - Retrieve by UUID
  - `get_r2_package()` - Retrieve by name and version
  - `update_r2_package()` - Update package metadata
  - `delete_r2_package()` - Soft/hard delete with cascade handling
  - `list_user_r2_packages()` - List user's packages with pagination
  - `list_public_r2_packages()` - List public packages
  - `check_r2_package_exists()` - Existence validation
  - `get_r2_download_history()` - Download history with pagination
- **Benefits**:
  - Schema isolation without PostgREST configuration changes
  - Explicit column ordering prevents type mismatches
  - Centralized business logic in database layer
  - Better security through `SECURITY DEFINER` functions

**2. Dynamic Schema Support**:
- Tables support configurable schema placement (not hardcoded to `public`)
- Schema name determined by `get_schema_name()` function in database
- Python application automatically detects and uses configured schema
- Default: `tests` schema for testing, `public` for production
- Benefits: Better environment isolation, testing flexibility

**3. Localhost-Only Upload Restriction**:
- Upload endpoint restricted to localhost access only (`127.0.0.1`, `::1`)
- Replaces user authentication with IP-based access control
- Designed for automated build/deployment systems on server
- Benefits: Enhanced security, prevents unauthorized external uploads

**4. System Uploader ID**:
- Default uploader ID: `00000000-0000-0000-0000-000000000000`
- System user created in `auth.users` table with email `system@localhost`
- Used when no specific user is provided for localhost uploads
- Allows package uploads without user authentication
- Foreign key constraint properly enforced

**5. Version Constraint Fix**:
- Corrected semantic version regex in check constraint
- Pattern: `^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.-]+)?(\+[a-zA-Z0-9.-]+)?$`
- Supports: `1.0.0`, `2.1.3-beta`, `1.0.0+build.123`, etc.
- Prevents invalid version strings at database level

### Upgrade Guide

If you have an existing R2 package system, follow these steps:

**Step 1: Backup existing data**
```bash
# Export existing packages
pg_dump -t public.r2_packages -t public.r2_package_downloads > backup_r2_packages.sql
```

**Step 2: Run new migrations**
```bash
# Initialize schema configuration (REQUIRED FIRST)
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -v ON_ERROR_STOP=1 \
  -f center_management/db/migration/sql_schema_migration/00_schema_init.sql

# Create R2 package system with RPC functions
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -v ON_ERROR_STOP=1 \
  -f center_management/db/migration/sql_schema_migration/r2_package_system.sql

# CRITICAL: Restart PostgREST to refresh schema cache
docker restart supabase-rest
sleep 3 && echo "PostgREST restarted"
```

**Step 3: Migrate data (if moving from public to tests schema)**
```bash
# Copy data from public to tests schema
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" <<EOF
INSERT INTO tests.r2_packages SELECT * FROM public.r2_packages;
INSERT INTO tests.r2_package_downloads SELECT * FROM public.r2_package_downloads;
EOF
```

**Step 4: Update application**
- Python application automatically uses new schema (no code changes needed)
- R2PackageConfig now calls `get_schema_name()` at initialization
- Restart application to pick up changes

**Step 5: Test upload restriction**
```bash
# From server (should work)
curl -X POST http://localhost:8001/r2/packages/upload \
  -F "file=@test.tar.gz" -F "package_name=test" -F "version=1.0.0"

# From external client (should return 403)
curl -X POST http://your-server-ip:8001/r2/packages/upload \
  -F "file=@test.tar.gz" -F "package_name=test" -F "version=1.0.0"
```

## Migration Guide

### From Local Storage

```python
import os
from pathlib import Path
from center_management.r2_storage import PackageManager

pm = PackageManager()
local_dir = Path("/local/packages")

for package_file in local_dir.glob("*.tar.gz"):
    # Parse package name and version from filename
    name, version = parse_filename(package_file.name)

    # Upload to R2
    pm.upload_package(
        package_name=name,
        version=version,
        file_obj=package_file,
        uploader_id=admin_user_id,
        is_public=True
    )
```

### From S3

```python
# Use boto3 to list S3 objects
# Download and re-upload to R2 using PackageManager
```

## License

This module is part of the web_backend project.

## Support

For issues or questions:
- Check logs: `center_management/logs/`
- Database queries: Use Supabase Studio
- R2 dashboard: Cloudflare dashboard

## Deployment Recommendations

### Production Setup

**1. Schema Configuration**:
```sql
-- For production, configure schema in 00_schema_init.sql
-- Option 1: Use public schema (default for production)
CREATE OR REPLACE FUNCTION get_schema_name() RETURNS TEXT AS $$
BEGIN
    RETURN 'public';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Option 2: Use custom schema for isolation
CREATE OR REPLACE FUNCTION get_schema_name() RETURNS TEXT AS $$
BEGIN
    RETURN 'packages';  -- Custom schema name
END;
$$ LANGUAGE plpgsql IMMUTABLE;
```

**2. Upload Automation**:
```bash
# Example: Automated deployment script (runs on server)
#!/bin/bash
# deploy_package.sh

PACKAGE_FILE=$1
PACKAGE_NAME=$2
VERSION=$3

# Upload via localhost API
curl -X POST http://localhost:8001/r2/packages/upload \
  -F "file=@${PACKAGE_FILE}" \
  -F "package_name=${PACKAGE_NAME}" \
  -F "version=${VERSION}" \
  -F "is_public=true"

# Example usage:
# ./deploy_package.sh my-app-1.2.3.tar.gz my-app 1.2.3
```

**3. SSH Tunnel for Remote Upload** (if needed):
```bash
# Create SSH tunnel to access localhost API remotely
ssh -L 8001:localhost:8001 user@server

# Now you can upload from your local machine via the tunnel
curl -X POST http://localhost:8001/r2/packages/upload \
  -F "file=@local-package.tar.gz" \
  -F "package_name=test" \
  -F "version=1.0.0"
```

**4. CI/CD Integration**:
```yaml
# Example: GitHub Actions workflow
name: Deploy Package
on:
  release:
    types: [published]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Build package
        run: |
          # Build your package
          tar -czf package.tar.gz ./dist

      - name: Deploy to server
        run: |
          # SSH to server and upload via localhost
          scp package.tar.gz user@server:/tmp/
          ssh user@server "curl -X POST http://localhost:8001/r2/packages/upload \
            -F 'file=@/tmp/package.tar.gz' \
            -F 'package_name=${{ github.event.repository.name }}' \
            -F 'version=${{ github.event.release.tag_name }}'"
```

### Security Checklist

- [ ] Upload endpoint only accessible via localhost
- [ ] Firewall rules block external access to port 8001 (or use reverse proxy)
- [ ] R2 credentials stored in environment variables, not in code
- [ ] Database RLS policies enabled on all package tables
- [ ] Download URLs have short expiration times (≤ 1 hour)
- [ ] Regular audit of public packages
- [ ] Monitoring and alerting for unusual upload/download patterns
- [ ] Backup strategy for package metadata

## Contributing

When contributing to this module:
1. Update database migrations for schema changes
2. Add tests to `tests/integration/test_r2_packages.py`
3. Update this README with new features
4. Follow existing code patterns and conventions
5. Test both localhost and external access for upload endpoint
6. Verify schema migration works with both `tests` and `public` schemas
