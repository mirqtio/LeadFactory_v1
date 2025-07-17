#!/bin/bash
# BPCI-UltraFast - Ultra-fast local CI validation (<3 minutes)
# Purpose: Immediate feedback that mirrors the Ultra-Fast CI Pipeline
# Runs absolute minimum tests for syntax and import validation

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
echo -e "${BLUE}===========================================${NC}"
echo -e "${BLUE}   BPCI-UltraFast - Instant Check (<3min)  ${NC}"
echo -e "${BLUE}===========================================${NC}"
echo ""

# Check if we can use existing venv
if [ -d ".venv" ] && [ -f ".venv/bin/python" ]; then
    info "Using existing virtual environment..."
    source .venv/bin/activate
else
    error "No .venv found. Run 'make bpci-fast' first to set up environment"
    exit 1
fi

# Set minimal environment
export PYTHONDONTWRITEBYTECODE=1
export USE_STUBS="false"
export ENVIRONMENT="test"
export SKIP_INFRASTRUCTURE="true"
export DATABASE_URL="sqlite:///:memory:"
# Disable ALL external features
export ENABLE_GBP="false"
export ENABLE_PAGESPEED="false"
export ENABLE_SENDGRID="false"
export ENABLE_OPENAI="false"
export ENABLE_DATAAXLE="false"
export ENABLE_HUNTER="false"
export ENABLE_SEMRUSH="false"
export ENABLE_SCREENSHOTONE="false"
export ENABLE_LIGHTHOUSE="false"
export ENABLE_LLM_AUDIT="false"

# Run smoke tests only (ultra-fast subset)
info "Running ultra-fast smoke tests..."
echo ""

# Run only smoke tests with aggressive timeout
if command -v timeout &> /dev/null; then
    # Use timeout if available
    timeout 120 python -m pytest \
        --tb=line \
        -q \
        -x \
        --maxfail=1 \
        --disable-warnings \
        -p no:warnings \
        --timeout=10 \
        --timeout-method=signal \
        tests/smoke/ \
        -k 'not integration'
else
    # Run without timeout on macOS
    python -m pytest \
        --tb=line \
        -q \
        -x \
        --maxfail=1 \
        --disable-warnings \
        -p no:warnings \
        --timeout=10 \
        --timeout-method=signal \
        tests/smoke/ \
        -k 'not integration'
fi

if [ $? -eq 0 ]; then
    success "Smoke tests passed!"
    TEST_RESULT=0
    
    # Run basic import checks
    info "Checking critical imports..."
    if python -c "
import sys
try:
    import api
    import d0_gateway
    import d1_targeting
    import d2_sourcing
    import d3_assessment
    import core
    print('✅ All critical imports successful')
    sys.exit(0)
except ImportError as e:
    print(f'❌ Import failed: {e}')
    sys.exit(1)
"; then
        success "Import validation passed!"
    else
        error "Import validation failed!"
        TEST_RESULT=1
    fi
else
    TEST_RESULT=$?
    error "Smoke tests failed with exit code: $TEST_RESULT"
fi

# Summary
echo ""
echo -e "${BLUE}===========================================${NC}"
if [ $TEST_RESULT -eq 0 ]; then
    success "BPCI-ULTRAFAST CHECK PASSED"
    echo -e "${GREEN}Basic validation successful!${NC}"
    echo ""
    echo "This was a minimal check. Consider running:"
    echo "  - 'make bpci-fast' for more thorough validation"
    echo "  - 'make bpci' for full CI validation"
else
    error "BPCI-ULTRAFAST CHECK FAILED"
    echo -e "${RED}Critical issues found - fix immediately${NC}"
fi
echo -e "${BLUE}===========================================${NC}"

exit $TEST_RESULT