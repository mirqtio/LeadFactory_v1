# P3-007 Error Handling & Cleanup Validation

## Overview
Comprehensive error handling and cleanup validation procedures for Docker CI test execution.

## Error Handling Validation Framework

### 1. Container Build Failures
**Scenario**: Docker image build fails due to missing dependencies or configuration errors

**Validation Steps**:
```bash
# Test build failure scenarios
# 1. Missing dependency
echo "RUN pip install non-existent-package==999.999.999" >> Dockerfile.test
docker build -f Dockerfile.test -t leadfactory-test .

# 2. Invalid base image
sed -i 's/python:3.11.0-slim/python:invalid-tag/' Dockerfile.test
docker build -f Dockerfile.test -t leadfactory-test .

# 3. Syntax errors in Dockerfile
echo "INVALID_INSTRUCTION" >> Dockerfile.test
docker build -f Dockerfile.test -t leadfactory-test .
```

**Expected Behavior**:
- [ ] Build failure detected and reported
- [ ] Comprehensive error messages in CI logs
- [ ] Dockerfile contents displayed for debugging
- [ ] Build process exits with non-zero code

### 2. Service Startup Failures
**Scenario**: PostgreSQL or stub-server fails to start properly

**Validation Steps**:
```bash
# Test PostgreSQL startup failure
# 1. Invalid database configuration
export POSTGRES_PASSWORD=""
docker compose -f docker-compose.test.yml up -d postgres

# 2. Port conflicts
docker run -d -p 5432:5432 postgres:15-alpine
docker compose -f docker-compose.test.yml up -d postgres

# 3. Network connectivity issues
docker network rm test-network
docker compose -f docker-compose.test.yml up -d
```

**Expected Behavior**:
- [ ] Service health checks detect failures
- [ ] Container logs are displayed
- [ ] Service status information provided
- [ ] Cleanup occurs even on startup failure

### 3. Test Execution Failures
**Scenario**: Test suite fails with various error conditions

**Validation Steps**:
```bash
# Test different failure scenarios
# 1. Import errors
echo "import non_existent_module" > test_import_error.py
pytest test_import_error.py

# 2. Database connection failures
export DATABASE_URL="postgresql://invalid:invalid@invalid:5432/invalid"
docker compose -f docker-compose.test.yml run --rm test

# 3. Timeout scenarios
# Add sleep to cause timeout
timeout 10 docker compose -f docker-compose.test.yml run --rm test
```

**Expected Behavior**:
- [ ] Test failures properly reported
- [ ] Exit codes propagated correctly
- [ ] Partial results extracted when possible
- [ ] Diagnostic information collected

### 4. Network Connectivity Issues
**Scenario**: Services cannot communicate with each other

**Validation Steps**:
```bash
# Test network issues
# 1. Service isolation
docker compose -f docker-compose.test.yml up -d postgres
docker compose -f docker-compose.test.yml run --rm test bash -c "ping postgres"

# 2. Port binding conflicts
docker run -d -p 5010:5010 nginx
docker compose -f docker-compose.test.yml up -d stub-server

# 3. DNS resolution issues
docker compose -f docker-compose.test.yml run --rm test bash -c "nslookup postgres"
```

**Expected Behavior**:
- [ ] Network connectivity tests run automatically
- [ ] Service-to-service communication verified
- [ ] DNS resolution problems detected
- [ ] Network diagnostic information provided

## Cleanup Validation Framework

### 1. Container Cleanup
**Scenario**: Ensure all containers are properly removed

**Validation Steps**:
```bash
# Test container cleanup
# 1. Normal completion
docker compose -f docker-compose.test.yml up -d
docker compose -f docker-compose.test.yml run --rm test
docker compose -f docker-compose.test.yml down -v

# 2. Failure scenarios
docker compose -f docker-compose.test.yml up -d
docker compose -f docker-compose.test.yml run --rm test sh -c "exit 1"
docker compose -f docker-compose.test.yml down -v

# 3. Forced cleanup
docker compose -f docker-compose.test.yml up -d
docker kill $(docker ps -q)
docker compose -f docker-compose.test.yml down -v
```

**Expected Behavior**:
- [ ] All containers removed after execution
- [ ] No orphaned containers remain
- [ ] Cleanup runs even on test failure
- [ ] Volume cleanup occurs properly

### 2. Volume Cleanup
**Scenario**: Ensure temporary volumes are properly cleaned up

**Validation Steps**:
```bash
# Test volume cleanup
# 1. Check volume creation
docker compose -f docker-compose.test.yml up -d
docker volume ls | grep leadfactory

# 2. Verify volume cleanup
docker compose -f docker-compose.test.yml down -v
docker volume ls | grep leadfactory

# 3. Persistent volume handling
docker compose -f docker-compose.test.yml up -d
docker compose -f docker-compose.test.yml down
docker volume ls | grep leadfactory
```

**Expected Behavior**:
- [ ] Temporary volumes removed with -v flag
- [ ] No dangling volumes left behind
- [ ] Host directories properly cleaned
- [ ] Persistent data handled appropriately

### 3. Network Cleanup
**Scenario**: Ensure Docker networks are properly cleaned up

**Validation Steps**:
```bash
# Test network cleanup
# 1. Check network creation
docker compose -f docker-compose.test.yml up -d
docker network ls | grep test-network

# 2. Verify network cleanup
docker compose -f docker-compose.test.yml down -v
docker network ls | grep test-network

# 3. Network isolation
docker network create test-conflict
docker compose -f docker-compose.test.yml up -d
```

**Expected Behavior**:
- [ ] Test networks removed after execution
- [ ] No orphaned networks remain
- [ ] Network conflicts handled gracefully
- [ ] Cleanup occurs in all scenarios

## Error Recovery Testing

### 1. Partial Failure Recovery
**Scenario**: Some services succeed while others fail

**Validation Steps**:
```bash
# Test partial failure scenarios
# 1. Database fails, stub-server succeeds
docker compose -f docker-compose.test.yml up -d stub-server
docker compose -f docker-compose.test.yml run --rm test

# 2. Stub-server fails, database succeeds
docker compose -f docker-compose.test.yml up -d postgres
docker compose -f docker-compose.test.yml run --rm test

# 3. Mixed service states
docker compose -f docker-compose.test.yml up -d postgres
docker kill $(docker ps -q --filter "name=postgres")
docker compose -f docker-compose.test.yml run --rm test
```

**Expected Behavior**:
- [ ] Partial failures properly detected
- [ ] Diagnostic information collected
- [ ] Appropriate error messages displayed
- [ ] Graceful degradation where possible

### 2. Resource Exhaustion Handling
**Scenario**: System resources become exhausted during execution

**Validation Steps**:
```bash
# Test resource exhaustion
# 1. Memory exhaustion
docker compose -f docker-compose.test.yml run --rm --memory=100m test

# 2. CPU limitation
docker compose -f docker-compose.test.yml run --rm --cpus=0.1 test

# 3. Disk space exhaustion
docker compose -f docker-compose.test.yml run --rm --tmpfs /tmp:size=1m test
```

**Expected Behavior**:
- [ ] Resource limits respected
- [ ] Graceful handling of resource exhaustion
- [ ] Appropriate error messages
- [ ] Cleanup occurs even with resource issues

## Validation Automation

### 1. Error Scenario Test Suite
```bash
#!/bin/bash
# Error handling validation script
echo "=== P3-007 Error Handling Validation ==="

# Track validation results
VALIDATION_RESULTS=""

# Test build failures
echo "Testing build failures..."
if test_build_failures; then
    VALIDATION_RESULTS="$VALIDATION_RESULTS\n✅ Build failure handling"
else
    VALIDATION_RESULTS="$VALIDATION_RESULTS\n❌ Build failure handling"
fi

# Test service failures
echo "Testing service failures..."
if test_service_failures; then
    VALIDATION_RESULTS="$VALIDATION_RESULTS\n✅ Service failure handling"
else
    VALIDATION_RESULTS="$VALIDATION_RESULTS\n❌ Service failure handling"
fi

# Test cleanup
echo "Testing cleanup procedures..."
if test_cleanup_procedures; then
    VALIDATION_RESULTS="$VALIDATION_RESULTS\n✅ Cleanup procedures"
else
    VALIDATION_RESULTS="$VALIDATION_RESULTS\n❌ Cleanup procedures"
fi

echo "=== Validation Results ==="
echo -e "$VALIDATION_RESULTS"
```

### 2. Monitoring Integration
```yaml
# Add to GitHub Actions workflow
- name: Error Handling Validation
  if: always()
  run: |
    echo "::group::Error Handling Validation"
    scripts/validate_error_handling.sh
    echo "::endgroup::"
```

### 3. Continuous Validation
- Run error handling tests on every CI execution
- Monitor for new failure modes
- Update validation procedures as needed
- Track error handling effectiveness

## Success Criteria
- All error scenarios properly handled
- Comprehensive error reporting in all cases
- Complete cleanup in success and failure scenarios
- No resource leaks or orphaned processes
- Error recovery procedures validated