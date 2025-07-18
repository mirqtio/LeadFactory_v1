# P3-007 Performance Benchmarking Plan

## Overview
Comprehensive performance monitoring strategy for Docker CI test execution validation.

## Performance Targets

### Primary Metrics
- **Total Test Execution Time**: < 5 minutes (300 seconds)
- **Docker Build Time**: < 2 minutes (120 seconds)
- **Service Startup Time**: < 1 minute (60 seconds)
- **Test Suite Execution**: < 3 minutes (180 seconds)

### Secondary Metrics
- **Memory Usage**: < 2GB peak utilization
- **CPU Usage**: < 80% average during test execution
- **Network Latency**: < 10ms between services
- **Coverage Report Generation**: < 30 seconds

## Benchmarking Strategy

### 1. Baseline Measurement
```bash
# Create benchmarking script
scripts/benchmark_ci.sh

# Measure Docker build time
time docker build -f Dockerfile.test -t leadfactory-test .

# Measure service startup time
time docker compose -f docker-compose.test.yml up -d

# Measure test execution time
time docker compose -f docker-compose.test.yml run --rm test
```

### 2. Continuous Monitoring
- **CI Integration**: Add timing measurements to GitHub Actions
- **Trend Analysis**: Track performance over time
- **Alerting**: Notify when performance degrades > 20%

### 3. Performance Test Matrix
```yaml
scenarios:
  - name: "Full Test Suite"
    command: "python -m pytest -v -n 2 --cov=."
    target: "< 180 seconds"
  
  - name: "Quick Tests Only"
    command: "python -m pytest -v -n 2 -m 'not slow'"
    target: "< 120 seconds"
  
  - name: "Single Worker"
    command: "python -m pytest -v --cov=."
    target: "< 300 seconds"
  
  - name: "Parallel Workers"
    command: "python -m pytest -v -n 4 --cov=."
    target: "< 150 seconds"
```

## Resource Monitoring

### 1. Docker Container Metrics
```bash
# Monitor container resource usage
docker stats --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

# Check container logs for performance issues
docker compose -f docker-compose.test.yml logs --follow test
```

### 2. System Resource Tracking
- **GitHub Actions Runner**: Monitor runner resource utilization
- **Database Performance**: Track PostgreSQL connection time and query performance
- **Network Performance**: Monitor service-to-service communication

### 3. Performance Degradation Detection
```bash
# Performance regression detection
if [ "$TEST_DURATION" -gt 300 ]; then
    echo "::warning::Test execution time exceeded 5 minutes: ${TEST_DURATION}s"
    echo "::warning::Consider investigating performance regression"
fi
```

## Optimization Strategies

### 1. Docker Layer Optimization
- **Multi-stage builds**: Minimize final image size
- **Dependency caching**: Cache pip installations
- **Build context optimization**: Use .dockerignore

### 2. Test Parallelization
- **Worker count tuning**: Balance between speed and resource usage
- **Test distribution**: Optimize test distribution across workers
- **Resource isolation**: Prevent test interference

### 3. Service Optimization
- **Database connections**: Pool connections efficiently
- **Service startup**: Optimize service initialization
- **Network optimization**: Minimize network overhead

## Performance Validation Checklist

### Pre-Execution Validation
- [ ] Verify Docker daemon is running optimally
- [ ] Check available system resources
- [ ] Validate network connectivity
- [ ] Confirm test environment is clean

### During Execution Monitoring
- [ ] Monitor CPU usage throughout test run
- [ ] Track memory consumption patterns
- [ ] Observe network traffic between services
- [ ] Check for resource contention

### Post-Execution Analysis
- [ ] Analyze test execution times by category
- [ ] Review resource utilization patterns
- [ ] Identify performance bottlenecks
- [ ] Generate performance report

## Benchmarking Implementation

### 1. Automated Performance Testing
```bash
#!/bin/bash
# Performance benchmarking script
echo "=== P3-007 Performance Benchmark ==="
echo "Timestamp: $(date)"

# Measure Docker build time
echo "Building Docker image..."
BUILD_START=$(date +%s)
docker build -f Dockerfile.test -t leadfactory-test .
BUILD_END=$(date +%s)
BUILD_TIME=$((BUILD_END - BUILD_START))

# Measure service startup time
echo "Starting services..."
STARTUP_START=$(date +%s)
docker compose -f docker-compose.test.yml up -d
STARTUP_END=$(date +%s)
STARTUP_TIME=$((STARTUP_END - STARTUP_START))

# Measure test execution time
echo "Running tests..."
TEST_START=$(date +%s)
docker compose -f docker-compose.test.yml run --rm test
TEST_END=$(date +%s)
TEST_TIME=$((TEST_END - TEST_START))

# Calculate total time
TOTAL_TIME=$((BUILD_TIME + STARTUP_TIME + TEST_TIME))

echo "=== Performance Results ==="
echo "Docker Build Time: ${BUILD_TIME}s"
echo "Service Startup Time: ${STARTUP_TIME}s"
echo "Test Execution Time: ${TEST_TIME}s"
echo "Total Time: ${TOTAL_TIME}s"

# Validate against targets
if [ $TOTAL_TIME -lt 300 ]; then
    echo "✅ Performance target met (< 5 minutes)"
else
    echo "❌ Performance target exceeded (> 5 minutes)"
fi
```

### 2. CI Integration
```yaml
# Add to GitHub Actions workflow
- name: Performance Benchmarking
  run: |
    echo "::group::Performance Benchmarking"
    scripts/benchmark_ci.sh
    echo "::endgroup::"
```

### 3. Performance Reporting
- Generate performance reports after each CI run
- Track performance trends over time
- Alert on performance regressions
- Provide optimization recommendations

## Success Criteria
- All performance targets consistently met
- No performance regressions detected
- Resource utilization within acceptable limits
- Performance monitoring integrated into CI pipeline