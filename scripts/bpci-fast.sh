#!/bin/bash
# BPCI-Fast - Fast local CI validation (<5 minutes)
# Purpose: Quick validation that mirrors the Fast CI Pipeline
# Uses Python directly without Docker for speed

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
echo -e "${BLUE}   BPCI-Fast - Quick CI Check (<5min)  ${NC}"
echo -e "${BLUE}======================================${NC}"
echo ""

# Check Python version
info "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
if [[ ! "$PYTHON_VERSION" =~ ^3\.(11|12)$ ]]; then
    error "Python 3.11+ required, found: $PYTHON_VERSION"
    exit 1
fi
success "Python $PYTHON_VERSION detected"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv-fast" ]; then
    info "Creating dedicated fast virtual environment..."
    python3 -m venv .venv-fast
fi

# Activate virtual environment
info "Activating virtual environment..."
source .venv-fast/bin/activate

# Install minimal dependencies
info "Installing minimal dependencies (cached)..."
pip install --quiet --upgrade pip
pip install --quiet pytest pytest-xdist pytest-timeout pytest-cov pytest-mock
pip install --quiet pydantic pydantic-settings python-dotenv httpx sqlalchemy fastapi requests
pip install --quiet redis faker stripe sendgrid twilio google-api-python-client openai psycopg2-binary alembic
pip install --quiet python-json-logger prometheus-client beautifulsoup4 pandas numpy tenacity aiohttp geopy
pip install --quiet click email-validator passlib[bcrypt] pyjwt python-multipart slowapi sentry-sdk[fastapi]
pip install --quiet pyyaml python-dateutil pytz cryptography jsonschema jinja2
pip install --quiet asyncpg GitPython PyGithub openpyxl websockets

success "Dependencies ready"

# Set environment for fast testing
export USE_STUBS="false"
export ENVIRONMENT="test"
export SKIP_INFRASTRUCTURE="true"
export DATABASE_URL="sqlite:///:memory:"
# Disable all external providers
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

# Create test directories
mkdir -p coverage test-results

# Run fast test suite
info "Running fast test suite..."
echo ""

# Run tests with 3-minute timeout
TEST_CMD="python -m pytest \
    --tb=no \
    -q \
    -x \
    --maxfail=1 \
    --disable-warnings \
    -p no:warnings \
    --timeout=15 \
    --timeout-method=signal \
    -n 2 \
    -m 'not slow and not integration and not phase_future' \
    tests/unit/ \
    tests/smoke/"

# Check if timeout command is available
if command -v timeout &> /dev/null; then
    TEST_RUNNER="timeout 180 $TEST_CMD"
else
    # On macOS, run without timeout
    TEST_RUNNER="$TEST_CMD"
fi

if eval $TEST_RUNNER; then
    success "Fast tests passed!"
    TEST_RESULT=0
else
    TEST_RESULT=$?
    error "Fast tests failed with exit code: $TEST_RESULT"
fi

# Summary
echo ""
echo -e "${BLUE}======================================${NC}"
if [ $TEST_RESULT -eq 0 ]; then
    success "BPCI-FAST CHECK PASSED"
    echo -e "${GREEN}Quick validation successful!${NC}"
    echo ""
    echo "Next steps:"
    echo "  - Run 'make bpci' for full validation before pushing"
    echo "  - Or push to get full CI validation"
else
    error "BPCI-FAST CHECK FAILED"
    echo -e "${RED}Fix the issues above before proceeding${NC}"
fi
echo -e "${BLUE}======================================${NC}"

# Deactivate virtual environment
deactivate

exit $TEST_RESULT