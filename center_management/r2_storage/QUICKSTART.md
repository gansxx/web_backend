# R2 Package Management - Quick Start Guide

Get your R2 package distribution system up and running in 5 minutes.

## Prerequisites

- Cloudflare account with R2 enabled
- PostgreSQL database (Supabase)
- Python 3.12+ with `uv` package manager
- Running backend service

## Step 1: Create R2 Bucket

1. Log into Cloudflare Dashboard
2. Navigate to **R2** → **Create Bucket**
3. Bucket name: `software-packages` (or your choice)
4. Copy your **Account ID** from R2 overview

## Step 2: Generate R2 API Token

1. Go to **R2** → **Manage R2 API Tokens**
2. Click **Create API Token**
3. Permissions: **Object Read & Write**
4. Save **Access Key ID** and **Secret Access Key**

## Step 3: Configure Environment

Add to your `.env` file:

```bash
# Cloudflare R2 Configuration
R2_ACCOUNT_ID=your_account_id_here
R2_ACCESS_KEY_ID=your_access_key_here
R2_SECRET_ACCESS_KEY=your_secret_key_here
R2_BUCKET_NAME=software-packages

# Optional settings
R2_MAX_PACKAGE_SIZE_MB=500
R2_DOWNLOAD_URL_EXPIRY_SECONDS=3600
```

## Step 4: Run Database Migration

```bash
# Load environment variables
source .env

# Run R2 package system migration
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -v ON_ERROR_STOP=1 \
  -f supabase/migrations/r2_package_system.sql
```

Expected output:
```
NOTICE:  R2 Package Management System schema created successfully
```

## Step 5: Verify Setup

```bash
# Start your backend service
uv run python run.py

# In another terminal, test health endpoint
curl http://localhost:8001/r2/packages/health
```

Expected response:
```json
{
  "status": "healthy",
  "r2_connection": true,
  "database_connection": true,
  "timestamp": "2025-10-15T10:00:00Z"
}
```

## Step 6: Upload Your First Package

### Using curl:

```bash
# Login first to get access token
curl -X POST http://localhost:8001/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}'

# Upload package (replace YOUR_TOKEN)
curl -X POST http://localhost:8001/r2/packages/upload \
  -H "Cookie: access_token=YOUR_TOKEN" \
  -F "file=@your-package-1.0.0.tar.gz" \
  -F "package_name=your-package" \
  -F "version=1.0.0" \
  -F "description=My first package" \
  -F "is_public=true"
```

### Using Python:

```python
from center_management.r2_storage import PackageManager
from pathlib import Path

# Initialize package manager
pm = PackageManager()

# Upload package
result = pm.upload_package(
    package_name="my-tool",
    version="1.0.0",
    file_obj=Path("./my-tool-1.0.0.tar.gz"),
    uploader_id="your-user-id",
    description="My awesome CLI tool",
    tags=["cli", "python"],
    is_public=True
)

print(f"✅ Uploaded: {result['package_name']} v{result['version']}")
print(f"📦 Size: {result['file_size'] / 1024:.2f} KB")
print(f"🔐 Hash: {result['file_hash'][:16]}...")
```

## Step 7: Download Package

```bash
# Generate download URL (no auth required for public packages)
curl http://localhost:8001/r2/packages/my-tool/1.0.0/download

# Response includes presigned URL
{
  "package_name": "my-tool",
  "version": "1.0.0",
  "download_url": "https://...",
  "expires_in": 3600,
  "file_size": 1048576,
  "file_hash": "sha256..."
}

# Download the file
wget <download_url>
```

## Common Tasks

### List All Public Packages

```bash
curl http://localhost:8001/r2/packages/public
```

### Search Packages

```bash
curl -X POST http://localhost:8001/r2/packages/search \
  -H "Content-Type: application/json" \
  -d '{
    "search_term": "cli",
    "limit": 10
  }'
```

### View Package Statistics

```bash
curl http://localhost:8001/r2/packages/stats/my-tool
```

### List Your Uploads

```bash
curl http://localhost:8001/r2/packages/my-uploads \
  -H "Cookie: access_token=YOUR_TOKEN"
```

### Update Package Metadata

```bash
curl -X PATCH http://localhost:8001/r2/packages/my-tool/1.0.0 \
  -H "Cookie: access_token=YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated description",
    "tags": ["cli", "python", "utility"]
  }'
```

## Troubleshooting

### "Package manager not initialized"

**Cause**: R2 credentials not configured or invalid

**Fix**:
1. Check `.env` file has all R2 variables
2. Verify credentials in Cloudflare dashboard
3. Restart backend service: `uv run python run.py`

### "R2 authentication failed"

**Cause**: Invalid R2 access keys

**Fix**:
1. Regenerate API token in Cloudflare R2 settings
2. Update `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`
3. Restart service

### "Package already exists"

**Cause**: Same package name and version already uploaded

**Fix**:
1. Use a different version number (e.g., 1.0.1)
2. Or delete existing version first (if you own it)

### Upload fails silently

**Cause**: File size exceeds limit

**Fix**:
1. Check file size: `ls -lh your-package.tar.gz`
2. Increase limit: `R2_MAX_PACKAGE_SIZE_MB=1000` in `.env`
3. Restart service

### Database connection errors

**Cause**: Database migration not run or connection issues

**Fix**:
```bash
# Test database connection
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -c "SELECT COUNT(*) FROM r2_packages;"

# Re-run migration if needed
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" \
  -f supabase/migrations/r2_package_system.sql
```

## Next Steps

1. **Set up Custom Domain** - Configure R2 custom domain for cleaner URLs
2. **Enable CDN** - Use Cloudflare CDN for faster global distribution
3. **Automate Cleanup** - Schedule cleanup of old packages
4. **Monitor Usage** - Track storage and bandwidth costs
5. **Add CI/CD** - Integrate package uploads into your build pipeline

## Example CI/CD Integration

### GitHub Actions

```yaml
name: Publish Package

on:
  release:
    types: [created]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Build package
        run: tar czf package-${{ github.ref_name }}.tar.gz .

      - name: Upload to R2
        run: |
          curl -X POST ${{ secrets.BACKEND_URL }}/r2/packages/upload \
            -H "Cookie: access_token=${{ secrets.API_TOKEN }}" \
            -F "file=@package-${{ github.ref_name }}.tar.gz" \
            -F "package_name=my-package" \
            -F "version=${{ github.ref_name }}" \
            -F "is_public=true"
```

## Security Best Practices

1. **Use Environment Variables** - Never commit credentials to git
2. **Rotate Keys Regularly** - Change R2 API tokens every 90 days
3. **Limit Token Permissions** - Use separate tokens for read vs write
4. **Enable IP Whitelist** - Restrict API access to known IPs
5. **Audit Downloads** - Review download logs regularly
6. **Validate File Integrity** - Always verify hashes after download

## Getting Help

- **Documentation**: [README.md](./README.md)
- **API Reference**: Check FastAPI docs at http://localhost:8001/docs
- **Database Schema**: See migration file for table structure
- **Code Examples**: Browse `center_management/r2_storage/` modules

Happy packaging! 🚀
