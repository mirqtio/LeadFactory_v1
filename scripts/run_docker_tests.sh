#!/bin/bash
# Docker test runner script with proper error handling

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

echo "=== Test Environment Setup ==="
echo "Creating output directories..."
mkdir -p /app/coverage /app/test-results

echo "Python version:"
python --version

echo "Working directory:"
pwd

echo "Environment variables:"
env | grep -E '(DATABASE_URL|USE_STUBS|STUB_BASE_URL|PYTHONPATH|CI)' | sort || true

echo "Installed packages:"
pip list | grep -E '(pytest|coverage)' || true

echo ""
echo "=== Running Database Migrations ==="
python scripts/run_migrations.py

echo ""
echo "=== Waiting for Stub Server ==="
python scripts/wait_for_stub.py

echo ""
echo "=== Verifying pytest installation ==="
# Check if pytest is available
if ! python -m pytest --version; then
    echo "ERROR: pytest not found! Installing pytest..."
    pip install pytest pytest-cov
fi

echo ""
echo "=== Checking Available Resources ==="
echo "CPU cores available: $(nproc)"
echo "Memory available: $(free -h 2>/dev/null | grep Mem: | awk '{print $2}' || echo 'Unknown')"

echo ""
echo "=== Starting Test Execution with Parallelization ==="
# Run pytest with parallelization
# Use conservative settings in Docker to avoid resource exhaustion
python -m pytest \
    -v \
    -n 2 \
    --dist worksteal \
    -m 'not slow and not phase_future' \
    --tb=short \
    --cov=. \
    --cov-report=html:/app/coverage/html \
    --cov-report=term \
    --cov-report=xml:/app/coverage/coverage.xml \
    --junitxml=/app/test-results/junit.xml \
    --cov-config=/app/.coveragerc \
    -p no:warnings \
    --durations=10

# Capture the exit code immediately
TEST_EXIT_CODE=$?

# If tests failed, try simpler command to get more info
if [ $TEST_EXIT_CODE -ne 0 ]; then
    echo "pytest command failed with exit code $TEST_EXIT_CODE"
    echo "Running simpler pytest command for debugging..."
    python -m pytest -v --tb=short || true
fi

echo ""
echo "=== Test Results ==="
echo "Coverage report location:"
ls -la /app/coverage/ 2>/dev/null || echo "No coverage directory"

echo "Test results location:"
ls -la /app/test-results/ 2>/dev/null || echo "No test-results directory"

echo "Copying coverage.xml to test-results..."
cp /app/coverage/coverage.xml /app/test-results/coverage.xml 2>/dev/null || echo "Could not copy coverage.xml"

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo "=== Test execution completed successfully ==="
else
    echo "=== Test execution failed with exit code $TEST_EXIT_CODE ==="
    exit $TEST_EXIT_CODE
fi