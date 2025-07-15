# Docker Network Configuration Fixes

## Overview
This document outlines the comprehensive Docker networking fixes implemented to resolve service connectivity issues that were causing test failures in the multi-container test environment.

## Issues Identified

### 1. Inconsistent Service Name Resolution
- **Problem**: Stub server health check used `localhost` instead of container service name
- **Impact**: Health checks failed in container environments
- **Solution**: Updated health check to use `127.0.0.1` and added proper DNS aliases

### 2. Environment Variable Confusion
- **Problem**: Complex logic in conftest.py trying to determine CI vs Docker vs local environments
- **Impact**: Wrong STUB_BASE_URL being set, causing connection failures
- **Solution**: Simplified environment detection logic with clear precedence

### 3. Network Configuration Issues
- **Problem**: No explicit network subnet, missing service aliases, inadequate health checks
- **Impact**: Intermittent connectivity issues, slow startup times
- **Solution**: Added dedicated subnet, service aliases, improved health checks

### 4. Insufficient Debugging Information
- **Problem**: Limited visibility into network connectivity issues
- **Impact**: Difficult to diagnose when services fail to communicate
- **Solution**: Added comprehensive network debugging tools

## Fixes Implemented

### 1. Docker Compose Configuration (`docker-compose.test.yml`)

#### Network Configuration
```yaml
networks:
  test-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

#### Service Improvements
- **PostgreSQL**: Added network aliases, improved health checks, restart policy
- **Stub Server**: Fixed health check URL, added network aliases, improved startup parameters
- **Test Service**: Enhanced environment variables, added network debugging info

#### Key Changes
- Added explicit subnet (172.20.0.0/16) for predictable IP allocation
- Service aliases for flexible hostname resolution
- Improved health check intervals and timeouts
- Added restart policies for better reliability

### 2. Test Configuration (`tests/conftest.py`)

#### Environment Detection
```python
is_docker_compose = os.environ.get("DOCKER_ENV") == "true"
is_github_actions = os.environ.get("CI") == "true" and os.environ.get("GITHUB_ACTIONS") == "true"
is_container = os.path.exists("/.dockerenv")
```

#### STUB_BASE_URL Logic
- Docker Compose: `http://stub-server:5010`
- GitHub Actions: `http://stub-server:5010`
- Local/Fallback: `http://localhost:5010`

#### Improved Error Handling
- Longer timeouts (60 attempts vs 30)
- Better error messages with environment context
- Detailed diagnostics on failures

### 3. Network Debugging Tools

#### `scripts/debug_network.py`
Comprehensive network diagnostics including:
- DNS resolution testing
- Port connectivity checks
- HTTP endpoint validation
- Container network interface inspection
- Environment variable display

#### `scripts/wait_for_stub.py` (Enhanced)
- Increased timeout and retries
- Better error categorization (connection, timeout, other)
- Network diagnostics on repeated failures
- Health check response validation

#### `scripts/validate_docker_network.sh`
End-to-end network validation:
- Docker Compose configuration validation
- Service startup verification
- Inter-service connectivity testing
- DNS resolution validation

### 4. GitHub Actions Improvements (`.github/workflows/main.yml`)

#### Enhanced Service Readiness Checks
- Increased timeouts (120s for stub server)
- Better curl parameters with timeouts
- Additional diagnostic commands on failures

#### Improved Error Diagnostics
- Network connectivity tests using nc, nslookup
- Service status and log inspection
- Environment variable verification

## Debugging Commands

### Quick Network Test
```bash
# Test current configuration
docker compose -f docker-compose.test.yml config --quiet

# Run network validation
./scripts/validate_docker_network.sh

# Debug network connectivity
python scripts/debug_network.py
```

### Service Connectivity Tests
```bash
# Test from within test container
docker compose -f docker-compose.test.yml run --rm test bash -c "
  nslookup stub-server
  nc -zv stub-server 5010
  curl -f http://stub-server:5010/health
"
```

### Manual Service Testing
```bash
# Start services
docker compose -f docker-compose.test.yml up -d postgres stub-server

# Check health
docker compose -f docker-compose.test.yml exec stub-server curl http://127.0.0.1:5010/health

# View logs
docker compose -f docker-compose.test.yml logs stub-server
```

## Monitoring and Maintenance

### Health Check Monitoring
- PostgreSQL: 3s interval, 10 retries, 10s start period
- Stub Server: 3s interval, 15 retries, 30s start period

### Network Troubleshooting Checklist
1. Verify Docker Compose configuration: `docker compose config`
2. Check service status: `docker compose ps`
3. Test DNS resolution: `nslookup service-name`
4. Test port connectivity: `nc -zv hostname port`
5. Check service logs: `docker compose logs service-name`
6. Run network diagnostics: `python scripts/debug_network.py`

### Common Issues and Solutions

#### "Connection Refused" Errors
- Check if service is actually listening on the port
- Verify health check is passing
- Ensure correct hostname is being used (service name vs localhost)

#### DNS Resolution Failures
- Verify services are on the same network
- Check network aliases configuration
- Restart containers if DNS cache is stale

#### Timeout Issues
- Increase health check timeouts
- Check service startup time
- Verify resource allocation

## Performance Optimizations

### Startup Time Improvements
- Parallel service startup with proper dependencies
- Optimized health check intervals
- Reduced unnecessary startup delays

### Resource Efficiency
- Dedicated network subnet prevents IP conflicts
- Restart policies prevent unnecessary container recreation
- Improved logging reduces noise

## Future Enhancements

### Monitoring
- Add Prometheus metrics for service connectivity
- Implement alerting for service health
- Container resource usage monitoring

### Testing
- Automated network connectivity tests
- Performance regression testing
- Chaos engineering for network resilience

### Documentation
- Service dependency mapping
- Network architecture diagrams
- Troubleshooting runbooks

## Files Modified

1. `/docker-compose.test.yml` - Network and service configuration
2. `/tests/conftest.py` - Environment detection and stub server setup
3. `/scripts/wait_for_stub.py` - Enhanced connectivity checking
4. `/scripts/run_docker_tests.sh` - Added network diagnostics
5. `/.github/workflows/main.yml` - Improved CI connectivity checks

## Files Created

1. `/scripts/debug_network.py` - Network debugging tool
2. `/scripts/validate_docker_network.sh` - Network validation script
3. `/DOCKER_NETWORK_FIXES.md` - This documentation

These fixes provide a robust, debuggable, and maintainable Docker networking setup that should resolve the connectivity issues causing test failures.