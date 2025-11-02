# Project Architecture Insights - Web Backend Center Management

## Service Architecture
The web backend uses a multi-service architecture with clear separation:

### Main Services
1. **main.py** (Port 8001)
   - Primary FastAPI application
   - Handles authentication, user data, orders
   - Uses Supabase integration
   - Includes CORS middleware for frontend

2. **orchestrationer.py** (Port 8002) 
   - Independent notification/webhook receiver
   - Handles bandwidth warnings, status updates
   - Now includes IP whitelist security
   - SSH integration for server management

### Key Patterns
- Each service runs on separate ports
- Independent FastAPI app instances
- No cross-service dependencies
- Environment-based configuration

### Security Implementation Pattern
- Middleware-based access control
- Environment variable configuration
- Comprehensive logging for auditing
- Proxy-aware IP detection

### Environment Management
- Uses conda environments (proxy_manage)
- Project follows Python package structure
- Separate test scripts for each component

## Development Workflow
- Services can be developed and deployed independently
- Clear separation of concerns
- Comprehensive documentation in README files
- Test scripts for validation

## Infrastructure
- Supabase for database and auth
- Docker Compose for local development
- SSH key management for server access
- DNS management integration