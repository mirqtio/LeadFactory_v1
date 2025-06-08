#!/bin/bash
set -e

echo "Starting stub server..."
# Start stub server in background
python -m uvicorn stubs.server:app --host 0.0.0.0 --port 5010 &
STUB_PID=$!

# Wait for stub server to be ready
echo "Waiting for stub server to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:5010/health > /dev/null 2>&1; then
        echo "Stub server is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Stub server failed to start"
        exit 1
    fi
    sleep 1
done

# Function to cleanup stub server on exit
cleanup() {
    echo "Cleaning up..."
    if [ ! -z "$STUB_PID" ]; then
        kill $STUB_PID 2>/dev/null || true
        wait $STUB_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Run tests
echo "Running tests..."
exec "$@"