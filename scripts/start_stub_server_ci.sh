#!/bin/bash
# Start stub server for CI environments
# This script ensures proper environment setup and error handling

set -e

echo "=== Starting Stub Server for CI ==="

# Set required environment variables
export USE_STUBS=true
export ENVIRONMENT=test
export STUB_BASE_URL=http://localhost:5010

# Ensure we're in the right directory
cd "${GITHUB_WORKSPACE:-$(pwd)}"

echo "Working directory: $(pwd)"
echo "Python version: $(python --version)"
echo "Environment variables set:"
echo "  USE_STUBS=$USE_STUBS"
echo "  ENVIRONMENT=$ENVIRONMENT"
echo "  STUB_BASE_URL=$STUB_BASE_URL"

# Check if port is available
if lsof -i :5010 >/dev/null 2>&1; then
    echo "ERROR: Port 5010 is already in use!"
    lsof -i :5010
    exit 1
fi

# Start the stub server
echo "Starting uvicorn..."
python -m uvicorn stubs.server:app \
    --host 127.0.0.1 \
    --port 5010 \
    --log-level info \
    --no-access-log &

STUB_PID=$!
echo "Stub server started with PID: $STUB_PID"

# Wait for server to be ready
echo "Waiting for stub server to be ready..."
MAX_ATTEMPTS=30
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ATTEMPT=$((ATTEMPT + 1))
    
    # Check if process is still running
    if ! kill -0 $STUB_PID 2>/dev/null; then
        echo "ERROR: Stub server process died!"
        exit 1
    fi
    
    # Try to connect
    if curl -s http://localhost:5010/health >/dev/null 2>&1; then
        echo "✅ Stub server is ready after $ATTEMPT attempts!"
        echo "Health check response:"
        curl -s http://localhost:5010/health | python -m json.tool
        
        # Save PID for cleanup
        echo $STUB_PID > stub_server.pid
        exit 0
    fi
    
    echo "Attempt $ATTEMPT/$MAX_ATTEMPTS: Waiting for stub server..."
    sleep 1
done

echo "ERROR: Stub server failed to start after $MAX_ATTEMPTS attempts!"
kill $STUB_PID 2>/dev/null || true
exit 1