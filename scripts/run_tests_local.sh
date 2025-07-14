#!/bin/bash
# Script to run tests locally with correct environment variables

# Override STUB_BASE_URL for local testing
export STUB_BASE_URL="http://localhost:5010"
export USE_STUBS=true
export ENVIRONMENT=test

# Run tests
echo "Running tests with local stub server configuration..."
python -m pytest "$@"