# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a production-ready SaaS backend combining Supabase infrastructure with Python FastAPI for custom business logic. The system provides:
- Complete user authentication and subscription management
- Payment processing with Chinese payment gateways
- Automated infrastructure management (VPS, DNS)
- Real-time order processing with automatic timeout handling

## Architecture

### Supabase Services
All Supabase services are containerized using Docker Compose:
- **Database**: PostgreSQL 15.8.1 with pg_cron extension
- **Auth**: GoTrue for authentication
- **API**: PostgREST for REST API
- **Realtime**: Realtime subscription service
- **Storage**: File storage service
- **Studio**: Management dashboard

### Python Backend Services
- **Main API Service**: FastAPI application (port 8001)
  - Framework: FastAPI with Pydantic models
  - Database: Supabase client for database operations
  - Authentication, user management, payments
- **Orchestrationer Service**: Independent FastAPI service (port 8002)
  - VPS/infrastructure management and monitoring
  - IP whitelist security middleware
  - Bandwidth warnings and status updates
- **Package Management**: uv for dependency management and virtual environment handling
- **Testing**: pytest with custom test scripts
- **Logging**: loguru for structured logging

## Common Commands

### Development Setup
```bash
# Install dependencies and set up project (uv handles virtual environment automatically)
uv sync

# Start Supabase services
docker compose up -d

# Stop unnecessary containers (optional)
docker stop supabase-vector realtime-dev.supabase-realtime supabase-storage supabase-edge-functions supabase-imgproxy

# Run main backend server
uv run python run.py  # Runs on port 8001 by default

# Run orchestrationer service (independent service)
cd center_management
uv run python orchestrationer.py    # Runs on port 8002
```

### Database Management
```bash
# Run database sql to test if the updated sql is ok in database
source .env
#the command can use to test if the connection to db is ok.It will back Hello world in normal situation 
 psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" -v ON_ERROR_STOP=1 -f supabase/migrations/test.sql
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" -v ON_ERROR_STOP=1 -f supabase/migrations/*.sql

```


### Testing
```bash
# Run main test
uv run python test_main.py

# Test specific features
uv run python test_free_plan_api.py    # Free plan functionality
uv run python test_ticket.py           # Ticket system
uv run python test_recall.py           # Password recovery
uv run python test_h5zhifu.py          # Payment integration

# Run database api tests
cd center_management/db && uv run python test_go_db.py

# Run all test scripts
cd center_management/db/test_scripts
for test in test_*.py; do uv run python "$test"; done

# Test orchestrationer service
cd center_management && uv run python test_ip_whitelist.py

# Run pytest
uv run pytest
```

## Key Modules

### Center Management (`center_management/`)
- **db/**: Database operations and configuration
  - `base_config.py`: Base Supabase configuration class
  - `order.py`: Order management with automatic timeout handling
  - `product.py`: Product management functionality
- **orchestrationer.py**: Independent FastAPI service for infrastructure management
  - IP whitelist security middleware
  - VPS monitoring and bandwidth warnings
  - Status update handling
- **node_manage.py**: VPS/node management system
- **vps_vultur_manage.py**: Vultr VPS provider integration
- **dns.py**: Tencent Cloud DNS management
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
   - Run tests before committing: `uv run pytest`

3. **Testing Strategy**:
   - All database functions must have pgtap tests
   - Python modules should have corresponding test scripts
   - Integration tests in `test_main.py`: `uv run python test_main.py`

## Important Notes

### Environment Management
- **Package Management**: Project uses `uv` for dependency management and virtual environment handling
- **No Manual Environment Activation**: `uv run` automatically manages the virtual environment
- **Dependency Installation**: Use `uv sync` to install all project dependencies
- **All Python Commands**: Prefix with `uv run` to ensure proper environment isolation

### Service Architecture
- **Main API Service**: Port 8001 (authentication, payments, user management)
- **Orchestrationer Service**: Port 8002 (VPS management, monitoring, IP whitelist)
- **Frontend**: Located in `/root/web_vpn_v0_test`

### Development Guidelines
- Never modify production database directly
- Use separate Supabase projects for each environment
- All database functions/triggers/indexes/policies must be code-reviewed
- The system uses automatic order timeout checking via pg_cron
- Payment processing is handled through h5zhifu integration
- DNS management uses Tencent Cloud SDK
- VPS management includes Vultr provider integration
- Infrastructure monitoring with automatic bandwidth warnings