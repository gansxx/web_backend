# Security Patterns and Best Practices - Learned from IP Whitelist Implementation

## IP Whitelist Security Pattern

### Implementation Strategy
- Use middleware approach for request interception
- Validate at the earliest possible point in request lifecycle
- Support both exact IP matching and CIDR network ranges
- Handle proxy environments with header inspection

### Code Pattern
```python
class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)
        if not self._is_ip_allowed(client_ip):
            # Log and reject
            return Response(status_code=403, content=json_error)
        # Continue processing
        return await call_next(request)
```

### Configuration Best Practices
- Use environment variables for IP lists
- Provide sensible defaults (localhost + private networks)
- Support comma-separated values for multiple IPs/networks
- Validate IP format on startup

### Logging Strategy
- Log both allowed and denied attempts
- Include IP, path, and method in logs
- Use appropriate log levels (INFO for allowed, WARNING for denied)
- Structured logging for easy parsing

## Proxy Environment Handling
Priority order for IP detection:
1. X-Forwarded-For header (first IP in list)
2. X-Real-IP header
3. Direct connection IP

## Error Handling Patterns
- Graceful handling of invalid IP addresses
- Clear error messages without exposing internals
- Fail securely (deny by default on errors)

## Performance Considerations
- Cache parsed IP networks for efficiency
- Minimal overhead per request (<1ms)
- Early rejection to save processing resources

## Testing Approach
- Unit tests for IP parsing logic
- Integration tests for HTTP request flow
- Test both valid and invalid scenarios
- Include proxy header testing