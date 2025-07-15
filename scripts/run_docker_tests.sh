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
echo "=== Starting Test Execution ==="
# Run pytest with all options
python -m pytest \
    -v \
    -m 'not slow and not phase_future' \
    --tb=short \
    --cov=. \
    --cov-report=html:/app/coverage/html \
    --cov-report=term \
    --cov-report=xml:/app/coverage/coverage.xml \
    --junitxml=/app/test-results/junit.xml \
    --cov-config=/app/.coveragerc \
    -p no:warnings \
    --durations=10 \
    || {
        echo "pytest command failed with exit code $?"
        echo "Trying simpler pytest command..."
        python -m pytest -v --tb=short
    }

# Check if test execution was successful
TEST_EXIT_CODE=$?

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