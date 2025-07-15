#!/bin/bash
# Debug script for Docker test execution issues

set -e

echo "=== Docker Test Debugging Script ==="
echo "This script helps diagnose issues with Docker test execution"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check Docker and Docker Compose
echo "Checking Docker installation..."
if command_exists docker; then
    echo -e "${GREEN}✓${NC} Docker is installed: $(docker --version)"
else
    echo -e "${RED}✗${NC} Docker is not installed"
    exit 1
fi

if command_exists docker-compose || docker compose version >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Docker Compose is available"
else
    echo -e "${RED}✗${NC} Docker Compose is not available"
    exit 1
fi

echo ""
echo "Checking Docker daemon..."
if docker info >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} Docker daemon is running"
else
    echo -e "${RED}✗${NC} Docker daemon is not running"
    exit 1
fi

echo ""
echo "=== Building Test Environment ==="
echo "Building test image..."
docker build -f Dockerfile.test -t leadfactory-test . || {
    echo -e "${RED}✗${NC} Failed to build test image"
    exit 1
}
echo -e "${GREEN}✓${NC} Test image built successfully"

echo ""
echo "=== Starting Services ==="
# Clean up any existing containers
docker compose -f docker-compose.test.yml down -v 2>/dev/null || true

# Start services
echo "Starting PostgreSQL..."
docker compose -f docker-compose.test.yml up -d postgres
sleep 5

echo "Checking PostgreSQL health..."
timeout 30 bash -c 'until docker compose -f docker-compose.test.yml exec -T postgres pg_isready -U postgres; do sleep 1; done' || {
    echo -e "${RED}✗${NC} PostgreSQL failed to start"
    docker compose -f docker-compose.test.yml logs postgres
    exit 1
}
echo -e "${GREEN}✓${NC} PostgreSQL is healthy"

echo ""
echo "Starting stub server..."
docker compose -f docker-compose.test.yml up -d stub-server
sleep 5

echo "Checking stub server health..."
timeout 30 bash -c 'until docker compose -f docker-compose.test.yml exec -T stub-server curl -f http://localhost:5010/health 2>/dev/null; do sleep 1; done' || {
    echo -e "${RED}✗${NC} Stub server failed to start"
    docker compose -f docker-compose.test.yml logs stub-server
    exit 1
}
echo -e "${GREEN}✓${NC} Stub server is healthy"

echo ""
echo "=== Testing Connectivity ==="
echo "Testing network connectivity between services..."
docker compose -f docker-compose.test.yml run --rm test bash -c "
    echo 'Testing database connection...'
    python -c \"
import psycopg2
try:
    conn = psycopg2.connect('postgresql://postgres:postgres@postgres:5432/leadfactory_test')
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print('❌ Database connection failed:', e)
\"
    echo ''
    echo 'Testing stub server connection...'
    curl -f http://stub-server:5010/health && echo '✅ Stub server connection successful' || echo '❌ Stub server connection failed'
" || true

echo ""
echo "=== Running Sample Test ==="
echo "Running a simple test to verify pytest works..."
docker compose -f docker-compose.test.yml run --rm test bash -c "
    cd /app
    python -m pytest --version
    echo ''
    echo 'Running a simple test...'
    python -c \"
import pytest

def test_simple():
    assert 1 + 1 == 2

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
\"
" || true

echo ""
echo "=== Environment Information ==="
docker compose -f docker-compose.test.yml run --rm test bash -c "
    echo 'Python packages:'
    pip list | grep -E '(pytest|coverage|psycopg2|alembic|fastapi|uvicorn)'
    echo ''
    echo 'Environment variables:'
    env | grep -E '(DATABASE_URL|USE_STUBS|STUB_BASE_URL|PYTHONPATH|CI)' | sort
"

echo ""
echo "=== Running Full Test Suite ==="
echo "This may take several minutes..."
echo ""

# Create directories for results
mkdir -p coverage test-results
chmod 777 coverage test-results

# Run the full test suite
if docker compose -f docker-compose.test.yml run --rm test; then
    echo -e "${GREEN}✓${NC} Tests completed successfully!"
    echo ""
    echo "Test results:"
    ls -la coverage/ 2>/dev/null || echo "No coverage directory"
    ls -la test-results/ 2>/dev/null || echo "No test-results directory"
else
    echo -e "${RED}✗${NC} Tests failed!"
    echo ""
    echo "Checking for partial results..."
    ls -la coverage/ 2>/dev/null || echo "No coverage directory"
    ls -la test-results/ 2>/dev/null || echo "No test-results directory"
fi

echo ""
echo "=== Cleanup ==="
read -p "Do you want to clean up the test environment? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker compose -f docker-compose.test.yml down -v
    echo -e "${GREEN}✓${NC} Test environment cleaned up"
else
    echo -e "${YELLOW}!${NC} Test environment left running for debugging"
    echo "To clean up manually, run: docker compose -f docker-compose.test.yml down -v"
fi

echo ""
echo "=== Debugging Complete ==="