#!/bin/bash
# Bulletproof CI v3 - Exact CI Environment Match
# This version uses Docker and PostgreSQL to match CI precisely
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "🚀 Bulletproof CI v3 - Exact CI Environment Replication"
echo "======================================================"
echo "This runs the EXACT same tests as GitHub CI using Docker"
echo ""

# Track failures
FAILURES=0
FAILURE_LOG=""

log_failure() {
    FAILURES=$((FAILURES + 1))
    FAILURE_LOG="${FAILURE_LOG}\n❌ $1"
    echo -e "${RED}❌ FAILED: $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ PASSED: $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  WARNING: $1${NC}"
}

log_info() {
    echo -e "${BLUE}ℹ️  INFO: $1${NC}"
}

# Cleanup function
cleanup() {
    echo -e "\n🧹 Cleaning up..."
    docker compose -f docker-compose.test.yml down -v 2>/dev/null || true
    rm -rf coverage/* test-results/* 2>/dev/null || true
}

# Set trap for cleanup on exit
trap cleanup EXIT

# 1. Pre-flight checks
echo -e "\n📋 Phase 1: Pre-flight Checks"
echo "=============================="

# Check Docker is running
if ! docker info >/dev/null 2>&1; then
    log_failure "Docker is not running. Please start Docker."
    exit 1
else
    log_success "Docker is running"
fi

# Check docker-compose
if ! command -v docker-compose >/dev/null 2>&1 && ! docker compose version >/dev/null 2>&1; then
    log_failure "docker-compose not found"
    exit 1
else
    log_success "docker-compose available"
fi

# 2. Build Test Image (same as CI)
echo -e "\n📋 Phase 2: Build Test Image"
echo "============================"
log_info "Building test image (this may take a minute)..."

if docker build -f Dockerfile.test -t leadfactory-test . >/tmp/bpci_docker_build.log 2>&1; then
    log_success "Test image built successfully"
else
    log_failure "Docker build failed"
    echo "Last 50 lines of build log:"
    tail -50 /tmp/bpci_docker_build.log
    exit 1
fi

# 3. Start Services (same as CI)
echo -e "\n📋 Phase 3: Start Services"
echo "========================="
log_info "Starting PostgreSQL and stub server..."

# Stop any existing containers
docker compose -f docker-compose.test.yml down -v >/dev/null 2>&1 || true

# Create directories
mkdir -p coverage test-results

# Start services
if docker compose -f docker-compose.test.yml up -d postgres stub-server >/tmp/bpci_compose_up.log 2>&1; then
    log_success "Services started"
else
    log_failure "Failed to start services"
    cat /tmp/bpci_compose_up.log
    exit 1
fi

# Wait for PostgreSQL
log_info "Waiting for PostgreSQL to be ready..."
POSTGRES_READY=false
for i in {1..60}; do
    if docker compose -f docker-compose.test.yml exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
        POSTGRES_READY=true
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

if [ "$POSTGRES_READY" = true ]; then
    log_success "PostgreSQL is ready"
else
    log_failure "PostgreSQL failed to start"
    docker compose -f docker-compose.test.yml logs postgres
    exit 1
fi

# Wait for stub server
log_info "Waiting for stub server to be ready..."
STUB_READY=false
for i in {1..60}; do
    if curl -f http://localhost:5010/health >/dev/null 2>&1; then
        STUB_READY=true
        break
    fi
    echo -n "."
    sleep 1
done
echo ""

if [ "$STUB_READY" = true ]; then
    log_success "Stub server is ready"
else
    log_failure "Stub server failed to start"
    docker compose -f docker-compose.test.yml logs stub-server
    exit 1
fi

# 4. Run Tests in Docker (EXACT same as CI)
echo -e "\n📋 Phase 4: Run Tests in Docker"
echo "==============================="
log_info "Running tests with exact CI configuration..."

# First check what command the test service will run
log_info "Test service command: $(docker compose -f docker-compose.test.yml config | grep -A1 'command:' | tail -1)"

# Run the exact same command as CI
if docker compose -f docker-compose.test.yml run --rm \
    -e CI=true \
    -e DOCKER_ENV=true \
    test >/tmp/bpci_test_output.log 2>&1; then
    log_success "All tests passed!"
    
    # Show summary
    echo -e "\n📊 Test Summary:"
    grep -E "passed|failed|errors|warnings" /tmp/bpci_test_output.log | tail -10 || true
else
    log_failure "Tests failed"
    
    # Show detailed failure information (same as CI)
    echo -e "\n=== Test Failures ==="
    grep -A5 -B5 "FAILED\|ERROR\|Error" /tmp/bpci_test_output.log | head -100 || true
    
    echo -e "\n=== Test Container Logs (last 200 lines) ==="
    docker compose -f docker-compose.test.yml logs --tail=200 test 2>/dev/null || true
    
    echo -e "\n=== PostgreSQL Container Logs ==="
    docker compose -f docker-compose.test.yml logs --tail=50 postgres 2>/dev/null || true
    
    echo -e "\n=== Stub Server Container Logs ==="
    docker compose -f docker-compose.test.yml logs --tail=50 stub-server 2>/dev/null || true
    
    echo -e "\n=== Container Status ==="
    docker compose -f docker-compose.test.yml ps
    
    # Set failure
    FAILURES=$((FAILURES + 1))
fi

# 5. Extract test results (same as CI)
echo -e "\n📋 Phase 5: Extract Test Results"
echo "================================"

# Get the test container ID
CONTAINER_ID=$(docker compose -f docker-compose.test.yml ps -q test 2>/dev/null | head -1)

if [ ! -z "$CONTAINER_ID" ]; then
    log_info "Extracting results from container $CONTAINER_ID"
    docker cp $CONTAINER_ID:/app/coverage.xml ./test-results/coverage.xml 2>/dev/null || log_warning "No coverage.xml found"
    docker cp $CONTAINER_ID:/app/junit.xml ./test-results/junit.xml 2>/dev/null || log_warning "No junit.xml found"
else
    # Check mounted volumes
    if [ -f "./coverage/coverage.xml" ]; then
        cp ./coverage/coverage.xml ./test-results/coverage.xml
        log_success "Coverage report extracted"
    fi
    if [ -f "./coverage/.coverage" ]; then
        log_success "Coverage data found"
    fi
fi

# Summary
echo -e "\n📊 BPCI v3 Summary"
echo "=================="
if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED! Your code matches CI exactly.${NC}"
    echo -e "${GREEN}Push with confidence - CI will pass.${NC}"
    exit 0
else
    echo -e "${RED}❌ $FAILURES CHECKS FAILED${NC}"
    echo -e "$FAILURE_LOG"
    echo -e "\n${YELLOW}These are the EXACT errors CI will encounter.${NC}"
    echo -e "${YELLOW}Fix them before pushing to avoid CI failures.${NC}"
    exit 1
fi