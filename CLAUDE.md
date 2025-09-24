# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Supabase backend project with a Python FastAPI application layer. The system provides:
- Supabase services (database, auth, storage, real-time, etc.)
- Python FastAPI backend with custom business logic
- Payment processing (h5zhifu integration)
- DNS management with Tencent Cloud
- Node/VPS management for infrastructure

## Architecture

### Supabase Services
All Supabase services are containerized using Docker Compose:
- **Database**: PostgreSQL 15.8.1 with pg_cron extension
- **Auth**: GoTrue for authentication
- **API**: PostgREST for REST API
- **Realtime**: Realtime subscription service
- **Storage**: File storage service
- **Studio**: Management dashboard

### Python Backend
- **Framework**: FastAPI with Pydantic models
- **Database**: Supabase client for database operations
- **Testing**: pytest with custom test scripts
- **Logging**: loguru for structured logging

## Common Commands

### Development Setup
```bash
# Set up Python environment
conda create -n "fastapi" python==3.12
conda activate fastapi
pip install -r requirements.txt

# Start Supabase services
docker compose up -d

# Stop unnecessary containers (optional)
docker stop supabase-vector realtime-dev.supabase-realtime supabase-storage supabase-edge-functions supabase-imgproxy

# Run backend server
python run.py  # Runs on port 8001 by default
```

### Database Management
```bash
# Generate database migration
supabase db diff -f "<description>"

# Reset database and apply migrations
supabase db reset

# Push changes to remote Supabase
supabase link && supabase db push

# Run database tests
psql "postgresql://postgres:postgres@localhost:54322/postgres" -v ON_ERROR_STOP=1 -f supabase/tests/db/*.sql
```

### Testing
```bash
# Run main test
python test_main.py

# Run database tests
cd center_management/db && python test_go_db.py

# Run all test scripts
cd center_management/db/test_scripts
for test in test_*.py; do python "$test"; done

# Run pytest
pytest
```

## Key Modules

### Center Management (`center_management/`)
- **db/**: Database operations and configuration
  - `base_config.py`: Base Supabase configuration class
  - `order.py`: Order management with automatic timeout handling
  - `product.py`: Product management functionality
- **node_manage.py**: VPS/node management system
- **encode_jwt.py**: JWT token generation utilities
- **test_api.py**: API testing utilities

### Routes (`routes/`)
- `auth.py`: Authentication endpoints
- `user_data.py`: User data management endpoints

### Payments (`payments/`)
- `h5zhifu.py`: H5 payment integration

### Database Migrations (`supabase/migrations/`)
All database changes must be managed through migration files in this directory.

## Database Features

### Automatic Order Timeout System
- Uses PostgreSQL pg_cron extension for automatic timeout checks
- Executes every 5 minutes to check and update expired orders
- Database functions: `check_and_expire_orders()`, `create_order_timeout_cron_job()`

### Data Models
- Orders with automatic timeout tracking
- Product management with user-specific data
- Authentication and user management

## Environment Configuration

Required environment variables:
```
FRONTEND_URL
POSTGRES_PASSWORD
JWT_SECRET
ANON_KEY
SERVICE_ROLE_KEY
DASHBOARD_USERNAME
DASHBOARD_PASSWORD
```

## Development Workflow

1. **Database Changes**:
   - Implement and test SQL locally in dev database
   - Generate migration: `supabase db diff -f "<description>"`
   - Write pgtap tests in `supabase/tests/db/`
   - Run all tests after reset: `supabase db reset`
   - Push to environment: `supabase link && supabase db push`

2. **Python Code Changes**:
   - Follow existing patterns in `center_management/db/`
   - Inherit from `BaseConfig` for database classes
   - Add tests to appropriate test files
   - Run tests before committing

3. **Testing Strategy**:
   - All database functions must have pgtap tests
   - Python modules should have corresponding test scripts
   - Integration tests in `test_main.py`

## Important Notes
- run `conda activate fastapi` to activate environment to run any py code
- make sure the fastapi environment is activate,then you can run `python run.py` to activate the backend api
- the front-end of the project is in `/root/web_vpn_v0_test`
- Never modify production database directly
- Use separate Supabase projects for each environment
- All database functions/triggers/indexes/policies must be code-reviewed
- The system uses automatic order timeout checking via pg_cron
- Payment processing is handled through h5zhifu integration
- DNS management uses Tencent Cloud SDK