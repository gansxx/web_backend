# Cloudflare R2 Package Management System

Complete software package distribution and storage solution integrated with your web backend.

## 📦 What's Been Created

### Core Modules

```
center_management/r2_storage/
├── __init__.py                 # Module initialization and exports
├── client.py                   # R2 storage client (boto3 S3-compatible)
├── package_manager.py          # High-level package management logic
├── models.py                   # Pydantic models for validation
├── exceptions.py               # Custom exception classes
├── README.md                   # Comprehensive documentation
└── QUICKSTART.md              # 5-minute setup guide
```

### Database Layer

```
center_management/db/
└── r2_package.py              # Database operations (CRUD, queries)

center_management/db/migration/sql_schema_migration/
└── r2_package_system.sql      # Database schema and functions
```

### API Routes

```
routes/
└── r2_packages.py             # RESTful API endpoints
```

### Configuration

```
.env.example                   # R2 configuration variables (updated)
main.py                   # Route registration (updated)
```

## 🚀 Quick Start

### 1. Configure Environment

```bash
# Add to .env
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_BUCKET_NAME=software-packages
```

### 2. Run Database Migration

```bash
source .env
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -v ON_ERROR_STOP=1 \
  -f center_management/db/migration/sql_schema_migration/r2_package_system.sql
```

### 3. Start Backend

```bash
uv run python run.py
```

### 4. Test System

```bash
curl http://localhost:8001/r2/packages/health
```

## 📚 Documentation

- **[README.md](center_management/r2_storage/README.md)** - Complete system documentation
  - Architecture overview
  - API endpoints reference
  - Python client usage
  - Database schema
  - Security and RLS policies
  - Performance optimization
  - Troubleshooting guide

- **[QUICKSTART.md](center_management/r2_storage/QUICKSTART.md)** - 5-minute setup guide
  - Step-by-step setup
  - First package upload
  - Common tasks
  - Troubleshooting tips
  - CI/CD integration examples

## 🔧 Key Features Implemented

### Package Management
- ✅ Multi-version support with semantic versioning
- ✅ Public and private package access control
- ✅ File integrity verification (SHA-256)
- ✅ Automatic download counting
- ✅ Full-text search with tags
- ✅ Package metadata management

### Storage & Distribution
- ✅ Cloudflare R2 integration (S3-compatible)
- ✅ Presigned download URLs with expiration
- ✅ Custom domain support
- ✅ Automatic cleanup of old versions
- ✅ Storage usage statistics

### Security
- ✅ Row Level Security (RLS) policies
- ✅ User-based access control
- ✅ Authentication integration with Supabase
- ✅ Audit logging (download history)

### API Endpoints (15 endpoints)
- ✅ Upload package (POST /r2/packages/upload)
- ✅ Download package (GET /r2/packages/{name}/{version}/download)
- ✅ Get package info (GET /r2/packages/{name}/{version})
- ✅ List versions (GET /r2/packages/{name}/versions)
- ✅ Search packages (POST /r2/packages/search)
- ✅ List public packages (GET /r2/packages/public)
- ✅ List my uploads (GET /r2/packages/my-uploads)
- ✅ Update metadata (PATCH /r2/packages/{name}/{version})
- ✅ Delete package (DELETE /r2/packages/{name}/{version})
- ✅ Package statistics (GET /r2/packages/stats/{name})
- ✅ Storage statistics (GET /r2/packages/stats/storage)
- ✅ Cleanup old packages (POST /r2/packages/cleanup)
- ✅ Verify integrity (GET /r2/packages/{name}/{version}/verify)
- ✅ Health check (GET /r2/packages/health)

## 📊 Database Schema

### Tables Created
- **r2_packages** - Package metadata and versions
- **r2_package_downloads** - Download history tracking

### Indexes Optimized
- Composite index: (package_name, version)
- GIN index: tags (JSONB)
- Time-based: created_at DESC
- Public filter: is_public

### Functions Implemented
- `record_r2_package_download()` - Track downloads
- `get_r2_package_stats()` - Package statistics
- `cleanup_old_r2_packages()` - Cleanup automation
- `search_r2_packages()` - Full-text search
- `get_r2_package_versions()` - Version listing

### RLS Policies
- Public packages readable by all
- Private packages readable by owner only
- Write operations require authentication
- Download history visible to owner

## 💻 Usage Examples

### Python Client

```python
from center_management.r2_storage import PackageManager
from pathlib import Path

pm = PackageManager()

# Upload
result = pm.upload_package(
    package_name="my-tool",
    version="1.0.0",
    file_obj=Path("./my-tool-1.0.0.tar.gz"),
    uploader_id=user_id,
    is_public=True
)

# Download URL
download = pm.download_package("my-tool", "1.0.0")
print(download['download_url'])

# Search
results = pm.search_packages(search_term="cli", tags=["python"])
```

### cURL Examples

```bash
# Upload package
curl -X POST http://localhost:8001/r2/packages/upload \
  -H "Cookie: access_token=TOKEN" \
  -F "file=@package.tar.gz" \
  -F "package_name=my-package" \
  -F "version=1.0.0" \
  -F "is_public=true"

# Download
curl http://localhost:8001/r2/packages/my-package/1.0.0/download

# Search
curl -X POST http://localhost:8001/r2/packages/search \
  -H "Content-Type: application/json" \
  -d '{"search_term": "cli", "limit": 10}'

# Statistics
curl http://localhost:8001/r2/packages/stats/storage
```

## 🔐 Security Considerations

### Authentication
- All write operations require valid Supabase authentication
- Token can be provided via cookie or Authorization header
- Public packages downloadable without authentication

### Access Control
- Package uploader controls visibility (public/private)
- Only uploader can modify or delete their packages
- Download history visible only to package owner

### File Integrity
- SHA-256 hash calculated on upload
- Hash verification available via API
- Presigned URLs expire after configured time

## 📈 Monitoring & Maintenance

### Health Checks
```bash
# System health
curl http://localhost:8001/r2/packages/health

# Storage stats
curl http://localhost:8001/r2/packages/stats/storage
```

### Database Queries
```sql
-- Total packages
SELECT COUNT(*) FROM r2_packages WHERE status = 'active';

-- Storage usage
SELECT package_name, SUM(file_size) as total_size
FROM r2_packages
WHERE status = 'active'
GROUP BY package_name;

-- Top downloaded
SELECT package_name, version, download_count
FROM r2_packages
ORDER BY download_count DESC
LIMIT 10;
```

### Cleanup Automation
```bash
# Preview cleanup (dry run)
curl -X POST http://localhost:8001/r2/packages/cleanup \
  -H "Cookie: access_token=TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"days_threshold": 90, "dry_run": true}'

# Execute cleanup
curl -X POST http://localhost:8001/r2/packages/cleanup \
  -H "Cookie: access_token=TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"days_threshold": 90, "dry_run": false}'
```

## 🚨 Troubleshooting

### Package Manager Not Initialized
```bash
# Check environment variables
env | grep R2_

# Verify R2 credentials
python -c "from center_management.r2_storage import R2Client; R2Client().list_files(max_keys=1)"

# Check logs
tail -f logs/app.log | grep -i "packagemanager\|r2"
```

### Upload Failures
- Check file size limit: `R2_MAX_PACKAGE_SIZE_MB`
- Verify R2 bucket exists and is accessible
- Ensure package name/version is valid (semantic versioning)
- Check authentication token is valid

### Database Errors
- Ensure migration has been run
- Verify PostgreSQL connection
- Check RLS policies are enabled
- Validate user has required permissions

## 🎯 Next Steps

### Production Deployment
1. Set up custom domain for R2 bucket
2. Enable Cloudflare CDN
3. Configure automated cleanup schedule
4. Set up monitoring alerts
5. Implement backup strategy

### CI/CD Integration
```yaml
# GitHub Actions example
- name: Upload to R2
  run: |
    curl -X POST ${{ secrets.BACKEND_URL }}/r2/packages/upload \
      -H "Cookie: access_token=${{ secrets.API_TOKEN }}" \
      -F "file=@${{ github.event.release.assets[0].url }}" \
      -F "package_name=${{ github.event.repository.name }}" \
      -F "version=${{ github.event.release.tag_name }}" \
      -F "is_public=true"
```

### Feature Enhancements
- [ ] Package version comparison API
- [ ] Automatic vulnerability scanning
- [ ] Download analytics dashboard
- [ ] Package deprecation warnings
- [ ] Multi-file packages (archives)
- [ ] Package dependencies tracking

## 📞 Support

For issues or questions:
1. Check documentation: [README.md](center_management/r2_storage/README.md)
2. Review logs: `tail -f logs/app.log`
3. Test database: `psql "postgresql://..." -c "SELECT COUNT(*) FROM r2_packages;"`
4. Verify R2 access: Check Cloudflare R2 dashboard

## 📄 License

This module is part of the web_backend project.

---

**Created**: 2025-10-15
**Version**: 1.0.0
**Status**: Production Ready ✅
