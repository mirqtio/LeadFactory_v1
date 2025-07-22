#!/bin/bash
# BPCI-Prod - Production Environment Mirror
# Purpose: Test against PostgreSQL to catch production-specific issues
# Uses the same PostgreSQL setup as production deployment

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
echo -e "${BLUE}======================================${NC}"
echo -e "${BLUE}  BPCI-Prod - Production Mirror      ${NC}"
echo -e "${BLUE}  PostgreSQL validation for prod     ${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Function to clean up on exit
cleanup() {
    info "Cleaning up Docker containers..."
    docker compose -f docker-compose.test.yml down -v 2>/dev/null || true
    docker rmi leadfactory-test:bpci-prod 2>/dev/null || true
}

# Set up trap to ensure cleanup happens
trap cleanup EXIT

# Step 1: Create necessary directories
info "Creating test directories..."
mkdir -p coverage test-results tmp
chmod 755 coverage test-results tmp

# Step 2: Lint and format check (production should also pass linting)
info "Running linting and format checks..."
echo "🔍 Running linting and format checks..."

if flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics; then
    success "Critical syntax check passed"
else
    error "Critical syntax check failed"
    exit 1
fi

if flake8 .; then
    success "Full linting passed"
else
    error "Full linting failed"
    exit 1
fi

if black . --check --line-length=120 --exclude="(.venv|venv)"; then
    success "Black formatting check passed"
else
    error "Black formatting check failed - run 'make format' to fix"
    exit 1
fi

if isort . --check-only --profile=black --line-length=120 --skip=.venv --skip=venv; then
    success "Import sorting check passed"
else
    error "Import sorting check failed - run 'make format' to fix"
    exit 1
fi

# Step 3: Build test image
info "Building production test Docker image..."
if docker build -f Dockerfile.test -t leadfactory-test:bpci-prod .; then
    success "Test image built successfully"
else
    error "Failed to build test image"
    exit 1
fi

# Step 4: Start PostgreSQL service
info "Starting PostgreSQL service..."
docker compose -f docker-compose.test.yml up -d postgres

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

# Step 5: Run production-focused test suite
info "Running production validation tests..."
echo "🚀 Running PostgreSQL-based test suite..."

TEST_CMD="docker compose -f docker-compose.test.yml run --rm test python -m pytest \
    -v \
    --tb=short \
    -n 2 \
    --dist worksteal \
    -m 'not slow and not phase_future' \
    --cov=core \
    --cov=d0_gateway \
    --cov-report=xml:/app/coverage/coverage.xml \
    --cov-report=term \
    --cov-fail-under=60 \
    --junitxml=/app/test-results/junit.xml \
    tests/unit/core/ \
    tests/unit/d0_gateway/ \
    tests/integration/"

if $TEST_CMD; then
    success "Production validation tests passed!"
    TEST_RESULT=0
else
    TEST_RESULT=$?
    error "Production validation tests failed with exit code: $TEST_RESULT"
    
    # Show logs on failure
    warning "Showing recent test logs:"
    docker compose -f docker-compose.test.yml logs test --tail=50
fi

# Step 6: Security scan
info "Running security scan..."
echo "🛡️ Running security scan..."
pip install bandit 2>/dev/null || warning "Could not install bandit"
bandit -r . -f json -o security-report.json -ll 2>/dev/null || true
if [ -f security-report.json ]; then
    success "Security scan completed"
else
    warning "Security scan could not complete"
fi

# Step 7: Check test results
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
    if coverage_pct < 60:
        print('WARNING: Coverage below 60% threshold')
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
echo -e "${BLUE}======================================${NC}"
if [ $TEST_RESULT -eq 0 ]; then
    success "BPCI-PROD CHECK PASSED"
    echo -e "${GREEN}✅ PostgreSQL validation successful!${NC}"
    echo -e "${GREEN}Code should work in production${NC}"
else
    error "BPCI-PROD CHECK FAILED"
    echo -e "${RED}❌ PostgreSQL issues found!${NC}"
    echo -e "${RED}Fix before deploying to production${NC}"
fi
echo -e "${BLUE}======================================${NC}"

exit $TEST_RESULT