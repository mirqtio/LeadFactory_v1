#!/bin/bash
# BPCI - Bulletproof CI Script
# Purpose: Catch bugs before they reach production by running the same tests as GitHub CI
# This script uses Docker Compose exactly like the CI workflow does

set -e  # Exit on error
set -o pipefail  # Exit on pipe failure

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions for colored output
info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

success() {
    echo -e "${GREEN}✅ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

# Header
echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}   BPCI - Bulletproof CI Check       ${NC}"
echo -e "${BLUE}   Full Validation: SQLite + PostgreSQL ${NC}"
echo -e "${BLUE}=======================================${NC}"
echo ""
info "Running comprehensive validation against both environments:"
info "• SQLite (GitHub CI mirror)"
info "• PostgreSQL (Production mirror)"
echo ""

# Function to clean up on exit
cleanup() {
    info "Cleaning up Docker containers..."
    docker compose -f docker-compose.test.yml down -v 2>/dev/null || true
}

# Set up trap to ensure cleanup happens
trap cleanup EXIT

# Step 1: Create necessary directories
info "Creating test directories..."
mkdir -p coverage test-results
chmod 777 coverage test-results

# Step 2: Build test image
info "Building test Docker image..."
if docker build -f Dockerfile.test -t leadfactory-test .; then
    success "Test image built successfully"
else
    error "Failed to build test image"
    exit 1
fi

# Step 3: Start services
info "Starting test services (postgres and stub-server)..."
docker compose -f docker-compose.test.yml up -d postgres stub-server

# Wait for PostgreSQL
info "Waiting for PostgreSQL to be ready..."
TIMEOUT=60
COUNTER=0
until docker compose -f docker-compose.test.yml exec -T postgres pg_isready -U postgres 2>/dev/null; do
    if [ $COUNTER -eq $TIMEOUT ]; then
        error "PostgreSQL failed to start within ${TIMEOUT} seconds"
        docker compose -f docker-compose.test.yml logs postgres
        exit 1
    fi
    echo -n "."
    sleep 1
    COUNTER=$((COUNTER + 1))
done
echo ""
success "PostgreSQL is ready"

# Wait for stub server
info "Waiting for stub server to be ready..."
COUNTER=0
until docker compose -f docker-compose.test.yml exec -T stub-server curl -f http://localhost:5010/health 2>/dev/null; do
    if [ $COUNTER -eq $TIMEOUT ]; then
        error "Stub server failed to start within ${TIMEOUT} seconds"
        docker compose -f docker-compose.test.yml logs stub-server
        exit 1
    fi
    echo -n "."
    sleep 2
    COUNTER=$((COUNTER + 2))
done
echo ""
success "Stub server is ready"

# Step 4: Run SQLite tests (GitHub CI mirror)
info "Phase 1: Running SQLite tests (GitHub CI mirror)..."
echo ""

SQLITE_RESULT=0
if bash scripts/bpci-fast.sh; then
    success "SQLite tests passed!"
else
    SQLITE_RESULT=$?
    error "SQLite tests failed with exit code: $SQLITE_RESULT"
fi

echo ""
echo -e "${BLUE}================================================${NC}"
echo ""

# Step 5: Run PostgreSQL tests (Production mirror)
info "Phase 2: Running PostgreSQL tests (Production mirror)..."
echo ""

POSTGRES_RESULT=0
if bash scripts/bpci-prod.sh; then
    success "PostgreSQL tests passed!"
else
    POSTGRES_RESULT=$?
    error "PostgreSQL tests failed with exit code: $POSTGRES_RESULT"
fi

# Determine overall result
if [ $SQLITE_RESULT -eq 0 ] && [ $POSTGRES_RESULT -eq 0 ]; then
    TEST_RESULT=0
    success "Both SQLite and PostgreSQL validation passed!"
else
    TEST_RESULT=1
    if [ $SQLITE_RESULT -ne 0 ]; then
        error "SQLite validation failed - GitHub CI will fail"
    fi
    if [ $POSTGRES_RESULT -ne 0 ]; then
        error "PostgreSQL validation failed - Production deployment at risk"
    fi
fi

# Step 5: Check test results
info "Checking test results..."
if [ -f "./coverage/coverage.xml" ]; then
    success "Coverage report generated"
    # Show coverage summary if available
    if command -v python3 &> /dev/null; then
        python3 -c "
import xml.etree.ElementTree as ET
try:
    tree = ET.parse('./coverage/coverage.xml')
    root = tree.getroot()
    line_rate = float(root.get('line-rate', 0))
    coverage_pct = line_rate * 100
    print(f'Coverage: {coverage_pct:.1f}%')
except:
    pass
" 2>/dev/null || true
    fi
else
    warning "No coverage report found"
fi

if [ -f "./test-results/junit.xml" ]; then
    success "JUnit report generated"
else
    warning "No JUnit report found"
fi

# Summary
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}              FINAL RESULTS                     ${NC}"
echo -e "${BLUE}================================================${NC}"

if [ $TEST_RESULT -eq 0 ]; then
    success "FULL BPCI VALIDATION PASSED"
    echo -e "${GREEN}✅ SQLite (GitHub CI): PASS${NC}"
    echo -e "${GREEN}✅ PostgreSQL (Production): PASS${NC}"
    echo ""
    echo -e "${GREEN}🚀 Safe to push and deploy!${NC}"
else
    error "BPCI VALIDATION FAILED"
    if [ $SQLITE_RESULT -ne 0 ]; then
        echo -e "${RED}❌ SQLite (GitHub CI): FAIL${NC}"
    else
        echo -e "${GREEN}✅ SQLite (GitHub CI): PASS${NC}"
    fi
    if [ $POSTGRES_RESULT -ne 0 ]; then
        echo -e "${RED}❌ PostgreSQL (Production): FAIL${NC}"
    else
        echo -e "${GREEN}✅ PostgreSQL (Production): PASS${NC}"
    fi
    echo ""
    echo -e "${RED}🚨 Fix issues before deployment${NC}"
fi
echo -e "${BLUE}================================================${NC}"

exit $TEST_RESULT