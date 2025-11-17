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
- **Heartbeat Detector Service**: Independent FastAPI service (port 8003)
  - IP and port availability monitoring
  - Distinguishes between IP-level and port-level failures
  - REST API for status queries and manual checks
  - Automatic periodic health checks
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

# Run heartbeat detector service (independent service)
uv run python center_management/heartbeat_detector.py  # Runs on port 8003
```

### Database Management
```bash
# Run database sql to test if the updated sql is ok in database
source .env

# Test database connection (should return "Hello world")
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" -v ON_ERROR_STOP=1 -f supabase/migrations/test.sql

# Run migrations from sql_schema_migration directory
# For migrations that require table ownership changes (e.g., 11_fix_table_ownership.sql):
PGPASSWORD=$POSTGRES_PASSWORD psql -U supabase_admin -h localhost -p 5438 -d postgres -v ON_ERROR_STOP=1 -f center_management/db/migration/sql_schema_migration/11_fix_table_ownership.sql

# For regular migrations (as postgres user):
psql "postgresql://postgres:$POSTGRES_PASSWORD@localhost:5438/postgres" -v ON_ERROR_STOP=1 -f center_management/db/migration/sql_schema_migration/12_stripe_integration.sql

# Run all pending migrations (from migration script)
# Note: Some migrations may require supabase_admin privileges
```


### Testing
```bash
# Run pytest (recommended)
uv run pytest

# Run main integration test (starts full API server)
uv run python run.py

# Test user addition functionality (NEW - integration tests)
uv run python tests/integration/test_free_plan_import.py     # Test imports
uv run python tests/integration/test_add_user_real.py        # Test actual user addition
uv run python tests/integration/test_add_user_real.py --help # See all options

# Test specific API features (integration tests)
uv run python test_free_plan_api.py    # Free plan functionality
uv run python test_ticket.py           # Ticket system
uv run python test_recall.py           # Password recovery
uv run python test_h5zhifu.py          # Payment integration

# Test database layer
cd center_management/db && uv run python test_go_db.py

# Test database order timeout system
cd center_management/db/test_scripts && uv run python test_order_timeout.py

# Test orchestrationer service
cd center_management && uv run python test_ip_whitelist.py

# Test heartbeat detector service
uv run python center_management/test_heartbeat.py
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
- **heartbeat_detector.py**: Independent FastAPI service for IP/port monitoring
  - Async concurrent port availability checks
  - Distinguishes IP-level vs port-level failures
  - REST API for status queries and manual checks
  - Configurable via JSON file or environment variables
  - See [docs/HEARTBEAT_DETECTOR.md](docs/HEARTBEAT_DETECTOR.md) for details
- **backend_api_v2.py**: User addition and subscription link generation (production module)
- **node_manage.py**: VPS/node management system
- **smart_port_manager.py**: Intelligent port allocation and management
- **vps_vultur_manage.py**: Vultr VPS provider integration
- **dns.py**: Tencent Cloud DNS management
- **encode_jwt.py**: JWT token generation utilities

### Routes (`routes/`)
- `auth.py`: Authentication endpoints
- `user_data.py`: User data management endpoints

### Payments (`payments/`)
- `h5zhifu.py`: H5 payment integration

### Database Migrations (`center_management/db/migration/sql_schema_migration`)
All database changes must be managed through migration files in this directory.

#### SQL Migration File Writing Rules

**CRITICAL**: All migration SQL files MUST follow these rules to ensure cross-environment compatibility:

1. **Never Hardcode Schema Names**
   - ❌ WRONG: `INSERT INTO products.r2_packages (...)`
   - ❌ WRONG: `SELECT * FROM production.orders`
   - ✅ CORRECT: Use dynamic schema via `get_schema_name()` function

2. **Always Use Dynamic Schema Pattern**
   ```sql
   DO $$
   DECLARE
       app_schema TEXT := get_schema_name();  -- Get schema dynamically
   BEGIN
       EXECUTE format('
           CREATE TABLE IF NOT EXISTS %I.table_name (
               id uuid PRIMARY KEY,
               ...
           )',
           app_schema  -- Use %I for identifier injection
       );
   END $$;
   ```

3. **Use `EXECUTE format()` for Dynamic SQL**
   - Use `%I` for identifiers (schema names, table names, column names)
   - Use `$1, $2, $3...` for values passed via USING clause
   - Quote literals with double single quotes: `''text''` inside format strings

4. **Required Dependencies**
   - All migration files MUST depend on `00_schema_init.sql` (or `20251017210439_schema_init.sql`)
   - Document dependencies in file header comments:
     ```sql
     -- =====================================================
     -- 功能说明
     -- =====================================================
     -- 前置依赖：
     --   1. 必须先执行 00_schema_init.sql 初始化 schema 配置
     --   2. 其他依赖的迁移文件
     -- =====================================================
     ```

5. **Example Pattern for INSERT/UPDATE/DELETE**
   ```sql
   DO $$
   DECLARE
       app_schema TEXT := get_schema_name();
       some_id UUID := 'a0000000-0000-0000-0000-000000000001';
   BEGIN
       EXECUTE format('
           INSERT INTO %I.table_name (id, name, value)
           VALUES ($1, $2, $3)
       ', app_schema)
       USING some_id, 'name_value', 100;
   END $$;
   ```

6. **Why This Matters**
   - Schema name is configurable via `schema_config` table (default: 'tests')
   - Different environments use different schemas: 'tests', 'production', etc.
   - Hardcoded schema names cause migration failures: `relation "products.table" does not exist`
   - Dynamic schema allows seamless migration across all environments

7. **Verification Checklist**
   - [ ] File uses `get_schema_name()` to obtain schema
   - [ ] All table references use `%I` placeholder with `app_schema` variable
   - [ ] No hardcoded schema names (search for `products.`, `tests.`, `production.`)
   - [ ] File header documents dependencies
   - [ ] Test execution: `psql ... -v ON_ERROR_STOP=1 -f migration_file.sql`

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
   - Place migration SQL files in `center_management/db/migration/sql_schema_migration/`
   - Test migrations by running them with psql (see Database Management commands)
   - Verify changes with database tests

2. **Python Code Changes**:
   - Follow existing patterns in `center_management/db/`
   - Inherit from `BaseConfig` for database classes (provides Supabase client)
   - Add tests to appropriate test files
   - Run tests before committing: `uv run pytest`

3. **API Endpoint Changes**:
   - Main API routes go in `routes/` directory
   - Orchestrationer endpoints go in `center_management/orchestrationer.py`
   - Use Pydantic models for request/response validation
   - Test with integration tests in root directory



## Documentation Management

### Session Documentation Organization

All documentation created during a development session should be organized by date to maintain clear version history and facilitate future reference.

**Rules**:
1. **Date-based Folders**: Create `docs/YYYY-MM-DD/` subfolder for each session
2. **Session Scope**: Move all documents created or significantly modified during the session
3. **Naming Convention**: Use descriptive names that reflect document purpose
4. **Index File**: Consider creating `docs/YYYY-MM-DD/README.md` for session summary

**Example Structure**:
```
docs/
├── 2025-10-27/
│   ├── ADVANCED_PLAN_INTEGRATION.md
│   ├── ADVANCED_PLAN_QUICKSTART.md
│   ├── ASYNC_DEPLOYMENT.md
│   ├── ASYNC_PRODUCT_GENERATION.md
│   └── MULTI_PAYMENT_USAGE_EXAMPLE.md
└── 2025-10-28/
    └── ...
```

**Document Types**:
- Integration guides (e.g., `*_INTEGRATION.md`)
- Quickstart guides (e.g., `*_QUICKSTART.md`)
- Deployment guides (e.g., `*_DEPLOYMENT.md`)
- Technical documentation (e.g., `*_DOCUMENTATION.md`)
- Usage examples (e.g., `*_USAGE_EXAMPLE.md`)

**Access Pattern**:
- Recent documentation: Check latest date folder
- Historical reference: Browse by date folders
- Cross-session topics: Use git log to track document evolution

## Important Notes

### Environment Management
- **Package Management**: Project uses `uv` for dependency management and virtual environment handling
- **No Manual Environment Activation**: `uv run` automatically manages the virtual environment
- **Dependency Installation**: Use `uv sync` to install all project dependencies
- **All Python Commands**: Prefix with `uv run` to ensure proper environment isolation

### Service Architecture
- **Main API Service** (`main.py` via `run.py`): Port 8001
  - Authentication, user management, payments
  - Routes in `routes/` directory (auth, user_data, ticket, free_plan)
  - Uses ANON_KEY for client authentication
- **Orchestrationer Service** (`center_management/orchestrationer.py`): Port 8002
  - Independent FastAPI service for infrastructure management
  - VPS monitoring, bandwidth warnings, status updates
  - IP whitelist security middleware
  - Uses SERVICE_ROLE_KEY for direct database access
- **Frontend**: Located in `/root/web_vpn_v0_test`
- **Database**: PostgreSQL via Supabase (localhost:5438)

### Development Guidelines
- Never modify production database directly
- Use separate Supabase projects for each environment
- All database functions/triggers/indexes/policies must be code-reviewed
- The system uses automatic order timeout checking via pg_cron
- Payment processing is handled through h5zhifu integration
- DNS management uses Tencent Cloud SDK
- VPS management includes Vultr provider integration
- Infrastructure monitoring with automatic bandwidth warnings