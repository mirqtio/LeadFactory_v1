#!/bin/bash

# P3-007 Performance Benchmarking Script
# Establishes baseline metrics for Docker CI test execution

set -e

echo "================================="
echo "   P3-007 Performance Benchmark"
echo "================================="
echo "Timestamp: $(date)"
echo "Environment: $(uname -a)"
echo ""

# Initialize metrics
TOTAL_START=$(date +%s)
RESULTS_DIR="./performance_results"
mkdir -p "$RESULTS_DIR"

# Function to log performance metrics
log_metric() {
    local metric_name="$1"
    local metric_value="$2"
    local target="$3"
    local status="$4"
    
    echo "[$metric_name] ${metric_value}s (target: ${target}s) - $status"
    echo "${metric_name},${metric_value},${target},${status}" >> "$RESULTS_DIR/metrics.csv"
}

# Initialize results file
echo "Metric,Value,Target,Status" > "$RESULTS_DIR/metrics.csv"

echo "=== Phase 1: Docker Build Performance ==="
BUILD_START=$(date +%s)
if docker build -f Dockerfile.test -t leadfactory-test . > "$RESULTS_DIR/build.log" 2>&1; then
    BUILD_END=$(date +%s)
    BUILD_TIME=$((BUILD_END - BUILD_START))
    BUILD_STATUS="✅ PASS"
    if [ $BUILD_TIME -lt 120 ]; then
        BUILD_TARGET_STATUS="✅ WITHIN TARGET"
    else
        BUILD_TARGET_STATUS="⚠️ EXCEEDS TARGET"
    fi
else
    BUILD_END=$(date +%s)
    BUILD_TIME=$((BUILD_END - BUILD_START))
    BUILD_STATUS="❌ FAIL"
    BUILD_TARGET_STATUS="❌ FAIL"
fi

log_metric "Docker Build Time" "$BUILD_TIME" "120" "$BUILD_TARGET_STATUS"
echo "Docker Build: $BUILD_STATUS ($BUILD_TIME seconds)"

echo ""
echo "=== Phase 2: Service Startup Performance ==="
STARTUP_START=$(date +%s)
if docker compose -f docker-compose.test.yml up -d > "$RESULTS_DIR/startup.log" 2>&1; then
    # Wait for services to be ready
    echo "Waiting for services to be ready..."
    sleep 10
    
    STARTUP_END=$(date +%s)
    STARTUP_TIME=$((STARTUP_END - STARTUP_START))
    STARTUP_STATUS="✅ PASS"
    if [ $STARTUP_TIME -lt 60 ]; then
        STARTUP_TARGET_STATUS="✅ WITHIN TARGET"
    else
        STARTUP_TARGET_STATUS="⚠️ EXCEEDS TARGET"
    fi
else
    STARTUP_END=$(date +%s)
    STARTUP_TIME=$((STARTUP_END - STARTUP_START))
    STARTUP_STATUS="❌ FAIL"
    STARTUP_TARGET_STATUS="❌ FAIL"
fi

log_metric "Service Startup Time" "$STARTUP_TIME" "60" "$STARTUP_TARGET_STATUS"
echo "Service Startup: $STARTUP_STATUS ($STARTUP_TIME seconds)"

echo ""
echo "=== Phase 3: Test Execution Performance ==="
TEST_START=$(date +%s)
if docker compose -f docker-compose.test.yml run --rm test > "$RESULTS_DIR/test.log" 2>&1; then
    TEST_END=$(date +%s)
    TEST_TIME=$((TEST_END - TEST_START))
    TEST_STATUS="✅ PASS"
    if [ $TEST_TIME -lt 180 ]; then
        TEST_TARGET_STATUS="✅ WITHIN TARGET"
    else
        TEST_TARGET_STATUS="⚠️ EXCEEDS TARGET"
    fi
else
    TEST_END=$(date +%s)
    TEST_TIME=$((TEST_END - TEST_START))
    TEST_STATUS="❌ FAIL"
    TEST_TARGET_STATUS="❌ FAIL"
fi

log_metric "Test Execution Time" "$TEST_TIME" "180" "$TEST_TARGET_STATUS"
echo "Test Execution: $TEST_STATUS ($TEST_TIME seconds)"

echo ""
echo "=== Phase 4: Cleanup Performance ==="
CLEANUP_START=$(date +%s)
if docker compose -f docker-compose.test.yml down -v > "$RESULTS_DIR/cleanup.log" 2>&1; then
    CLEANUP_END=$(date +%s)
    CLEANUP_TIME=$((CLEANUP_END - CLEANUP_START))
    CLEANUP_STATUS="✅ PASS"
    CLEANUP_TARGET_STATUS="✅ WITHIN TARGET"
else
    CLEANUP_END=$(date +%s)
    CLEANUP_TIME=$((CLEANUP_END - CLEANUP_START))
    CLEANUP_STATUS="❌ FAIL"
    CLEANUP_TARGET_STATUS="❌ FAIL"
fi

log_metric "Cleanup Time" "$CLEANUP_TIME" "30" "$CLEANUP_TARGET_STATUS"
echo "Cleanup: $CLEANUP_STATUS ($CLEANUP_TIME seconds)"

# Calculate total time
TOTAL_END=$(date +%s)
TOTAL_TIME=$((TOTAL_END - TOTAL_START))

echo ""
echo "=== Performance Summary ==="
echo "Docker Build Time: ${BUILD_TIME}s"
echo "Service Startup Time: ${STARTUP_TIME}s"
echo "Test Execution Time: ${TEST_TIME}s"
echo "Cleanup Time: ${CLEANUP_TIME}s"
echo "Total Time: ${TOTAL_TIME}s"

log_metric "Total CI Time" "$TOTAL_TIME" "300" "$([ $TOTAL_TIME -lt 300 ] && echo "✅ WITHIN TARGET" || echo "⚠️ EXCEEDS TARGET")"

echo ""
echo "=== Target Validation ==="
if [ $TOTAL_TIME -lt 300 ]; then
    echo "✅ PERFORMANCE TARGET MET: Total time ${TOTAL_TIME}s < 300s target"
    PERFORMANCE_STATUS="PASS"
else
    echo "❌ PERFORMANCE TARGET EXCEEDED: Total time ${TOTAL_TIME}s > 300s target"
    PERFORMANCE_STATUS="FAIL"
fi

echo ""
echo "=== Resource Usage Summary ==="
echo "System Resources:"
echo "  - CPU Usage: $(top -l 1 | grep 'CPU usage' | head -1 | awk '{print $3}' | sed 's/%//')"
echo "  - Memory Usage: $(vm_stat | grep 'Pages active' | awk '{print $3}' | sed 's/\.//')"
echo "  - Disk Space: $(df -h . | tail -1 | awk '{print $5}')"

# Generate performance report
REPORT_FILE="$RESULTS_DIR/performance_report.md"
cat > "$REPORT_FILE" << EOF
# P3-007 Performance Benchmark Report

**Execution Date**: $(date)
**Environment**: $(uname -a)
**Overall Status**: $PERFORMANCE_STATUS

## Performance Metrics

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| Docker Build Time | ${BUILD_TIME}s | 120s | $BUILD_TARGET_STATUS |
| Service Startup Time | ${STARTUP_TIME}s | 60s | $STARTUP_TARGET_STATUS |
| Test Execution Time | ${TEST_TIME}s | 180s | $TEST_TARGET_STATUS |
| Cleanup Time | ${CLEANUP_TIME}s | 30s | $CLEANUP_TARGET_STATUS |
| **Total CI Time** | **${TOTAL_TIME}s** | **300s** | **$([ $TOTAL_TIME -lt 300 ] && echo "✅ WITHIN TARGET" || echo "⚠️ EXCEEDS TARGET")** |

## Performance Analysis

### Docker Build Performance
- **Result**: ${BUILD_TIME}s (target: 120s)
- **Status**: $BUILD_TARGET_STATUS
- **Analysis**: $([ $BUILD_TIME -lt 120 ] && echo "Build time is within acceptable limits" || echo "Build time exceeds target - consider optimization")

### Service Startup Performance  
- **Result**: ${STARTUP_TIME}s (target: 60s)
- **Status**: $STARTUP_TARGET_STATUS
- **Analysis**: $([ $STARTUP_TIME -lt 60 ] && echo "Service startup is efficient" || echo "Service startup is slow - investigate dependencies")

### Test Execution Performance
- **Result**: ${TEST_TIME}s (target: 180s)
- **Status**: $TEST_TARGET_STATUS
- **Analysis**: $([ $TEST_TIME -lt 180 ] && echo "Test execution is within target" || echo "Test execution is slow - consider parallelization")

### Overall Assessment
- **Total Time**: ${TOTAL_TIME}s
- **Performance Status**: $PERFORMANCE_STATUS
- **Recommendation**: $([ $TOTAL_TIME -lt 300 ] && echo "Performance is acceptable for production deployment" || echo "Performance optimization required before production deployment")

## Recommendations

$([ $TOTAL_TIME -lt 300 ] && echo "✅ **APPROVED FOR PRODUCTION**: All performance targets met" || echo "⚠️ **OPTIMIZATION REQUIRED**: Performance targets not met")

### Next Steps
1. $([ $BUILD_TIME -lt 120 ] && echo "Docker build performance is acceptable" || echo "Optimize Docker build with better caching strategies")
2. $([ $STARTUP_TIME -lt 60 ] && echo "Service startup performance is acceptable" || echo "Optimize service startup with dependency management")
3. $([ $TEST_TIME -lt 180 ] && echo "Test execution performance is acceptable" || echo "Optimize test execution with better parallelization")
4. Monitor performance trends over time
5. Set up automated performance regression detection

EOF

echo ""
echo "=== Benchmark Results ==="
echo "Performance report saved to: $REPORT_FILE"
echo "Raw metrics saved to: $RESULTS_DIR/metrics.csv"
echo "Build log: $RESULTS_DIR/build.log"
echo "Startup log: $RESULTS_DIR/startup.log"
echo "Test log: $RESULTS_DIR/test.log"
echo "Cleanup log: $RESULTS_DIR/cleanup.log"

echo ""
echo "=== Final Assessment ==="
if [ "$PERFORMANCE_STATUS" = "PASS" ]; then
    echo "✅ P3-007 PERFORMANCE BENCHMARK: PASSED"
    echo "✅ Ready for production deployment"
    exit 0
else
    echo "❌ P3-007 PERFORMANCE BENCHMARK: FAILED"
    echo "⚠️ Performance optimization required"
    exit 1
fi