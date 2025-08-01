#!/bin/bash
# BPCI-Fast - Mirrors the actual GitHub CI Primary Pipeline exactly
# Purpose: Run the same tests as GitHub CI for accurate local validation
# Uses Docker container exactly like GitHub CI

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
echo -e "${BLUE}  BPCI-Fast - GitHub CI Mirror       ${NC}"
echo -e "${BLUE}  Exactly matches Primary CI Pipeline ${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Function to clean up on exit
cleanup() {
    info "Cleaning up..."
    docker rmi leadfactory-test:bpci-fast 2>/dev/null || true
}

# Set up trap to ensure cleanup happens
trap cleanup EXIT

# Step 1: Create necessary directories (same as GitHub CI)
info "Creating test directories..."
mkdir -p coverage test-results tmp
chmod 755 coverage test-results tmp

# Step 2: Lint and format check (same as GitHub CI)
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

# Step 3: Build test image (same as GitHub CI)
info "Building test Docker image..."
if docker build -f Dockerfile.test --target test -t leadfactory-test:bpci-fast .; then
    success "Test image built successfully"
else
    error "Failed to build test image"
    exit 1
fi

# Step 4: Run core test suite (exact same command as GitHub CI)
info "Running core validation tests..."
echo "🚀 Running core validation tests..."

TEST_CMD="docker run --rm \
  -e ENVIRONMENT=test \
  -e CI=true \
  -e PYTHONPATH=/app \
  -e DATABASE_URL=sqlite:///:memory: \
  -v $(pwd)/coverage:/app/coverage \
  -v $(pwd)/test-results:/app/test-results \
  -w /app \
  leadfactory-test:bpci-fast \
  python -m pytest \
    -x \
    --tb=short \
    -q \
    --disable-warnings \
    --timeout=30 \
    --timeout-method=signal \
    -n auto \
    --dist=loadfile \
    --cov=core \
    --cov=d0_gateway \
    --cov-report=xml:/app/coverage/coverage.xml \
    --cov-fail-under=60 \
    --junitxml=/app/test-results/junit.xml \
    tests/unit/core/ \
    tests/unit/d0_gateway/"

if $TEST_CMD; then
    success "Core validation tests passed!"
    TEST_RESULT=0
else
    TEST_RESULT=$?
    error "Core validation tests failed with exit code: $TEST_RESULT"
fi

# Step 5: Security scan (same as GitHub CI)
info "Running security scan..."
echo "🛡️ Running security scan..."
pip install bandit 2>/dev/null || warning "Could not install bandit"
bandit -r . -f json -o security-report.json -ll 2>/dev/null || true
if [ -f security-report.json ]; then
    success "Security scan completed"
else
    warning "Security scan could not complete"
fi

# Step 6: Check test results
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
    success "BPCI-FAST CHECK PASSED"
    echo -e "${GREEN}✅ Matches GitHub CI - Safe to push!${NC}"
    echo -e "${GREEN}Primary CI Pipeline will pass${NC}"
else
    error "BPCI-FAST CHECK FAILED"
    echo -e "${RED}❌ Fix issues above before pushing${NC}"
    echo -e "${RED}Primary CI Pipeline will fail${NC}"
fi
echo -e "${BLUE}======================================${NC}"

exit $TEST_RESULT