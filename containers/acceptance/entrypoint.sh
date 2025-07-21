#!/bin/bash
# Entrypoint script for Acceptance Runner Container
# PRP-1060: Containerized acceptance testing and SSH deployment automation

set -euo pipefail

# Container startup logging
echo "=== Acceptance Runner Container Starting ==="
echo "Container Version: 1.0.0"
echo "Timestamp: $(date -Iseconds)"
echo "User: $(whoami)"
echo "Working Directory: $(pwd)"

# Environment validation
echo "=== Environment Validation ==="

# Required environment variables
REQUIRED_VARS=(
    "REDIS_URL"
    "VPS_SSH_HOST"
    "VPS_SSH_USER"
    "PRP_ID"
)

for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        echo "ERROR: Required environment variable $var is not set"
        exit 1
    fi
    echo "✓ $var is set"
done

# Optional variables with defaults
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"
export VPS_SSH_KEY="${VPS_SSH_KEY:-/home/acceptance/.ssh/id_rsa}"
export ACCEPTANCE_TIMEOUT="${ACCEPTANCE_TIMEOUT:-600}"
export DEPLOYMENT_TIMEOUT="${DEPLOYMENT_TIMEOUT:-300}"

echo "✓ Environment validation complete"

# SSH key setup
echo "=== SSH Configuration ==="

# Check if SSH key exists or is provided via environment
if [[ -n "${SSH_PRIVATE_KEY:-}" ]]; then
    echo "Setting up SSH key from environment variable"
    echo "$SSH_PRIVATE_KEY" > /home/acceptance/.ssh/id_rsa
    chmod 600 /home/acceptance/.ssh/id_rsa
    echo "✓ SSH key configured from environment"
elif [[ -f "$VPS_SSH_KEY" ]]; then
    echo "✓ SSH key found at $VPS_SSH_KEY"
    chmod 600 "$VPS_SSH_KEY"
else
    echo "WARNING: No SSH key found. SSH deployment will fail."
fi

# SSH known hosts setup
if [[ -n "${VPS_SSH_HOST}" ]]; then
    echo "Adding $VPS_SSH_HOST to known hosts"
    ssh-keyscan -H "$VPS_SSH_HOST" >> /home/acceptance/.ssh/known_hosts 2>/dev/null || true
    echo "✓ SSH known hosts updated"
fi

# Git configuration
echo "=== Git Configuration ==="
git config --global user.name "Acceptance Runner"
git config --global user.email "acceptance@leadfactory.com"
git config --global init.defaultBranch main
echo "✓ Git configuration complete"

# Redis connectivity check
echo "=== Redis Connectivity ==="
if command -v redis-cli >/dev/null 2>&1; then
    if redis-cli -u "$REDIS_URL" ping >/dev/null 2>&1; then
        echo "✓ Redis connection successful"
    else
        echo "WARNING: Redis connection failed. Evidence storage may not work."
    fi
else
    echo "WARNING: redis-cli not available for connectivity test"
fi

# Python environment check
echo "=== Python Environment ==="
echo "Python version: $(python --version)"
echo "Pip packages installed: $(pip list | wc -l) packages"
echo "✓ Python environment ready"

# Workspace setup
echo "=== Workspace Setup ==="
cd /workspace

# Clone repository if GITHUB_REPO is provided
if [[ -n "${GITHUB_REPO:-}" ]]; then
    echo "Cloning repository: $GITHUB_REPO"
    if [[ -n "$GITHUB_TOKEN" ]]; then
        git clone "https://$GITHUB_TOKEN@github.com/$GITHUB_REPO.git" . 2>/dev/null || {
            echo "ERROR: Failed to clone repository with token"
            exit 1
        }
    else
        git clone "https://github.com/$GITHUB_REPO.git" . || {
            echo "ERROR: Failed to clone repository"
            exit 1
        }
    fi
    echo "✓ Repository cloned successfully"
fi

# Install additional dependencies if requirements.txt exists
if [[ -f "requirements.txt" ]]; then
    echo "Installing project dependencies"
    pip install --no-cache-dir -r requirements.txt
    echo "✓ Project dependencies installed"
fi

# Health check endpoint
echo "=== Starting Health Check Server ==="
# Start a simple health check server in the background
python -c "
import asyncio
from fastapi import FastAPI
import uvicorn
import threading
import time

app = FastAPI()

@app.get('/health')
async def health_check():
    return {'status': 'healthy', 'timestamp': time.time()}

def run_server():
    try:
        uvicorn.run(app, host='0.0.0.0', port=8080, log_level='warning')
    except Exception as e:
        print(f'Health server error: {e}')

# Start health server in background thread
thread = threading.Thread(target=run_server, daemon=True)
thread.start()
print('✓ Health check server started on port 8080')
" &

# Wait a moment for health server to start
sleep 2

# Execute the main command
echo "=== Executing Main Command ==="
echo "Command: $*"
echo "Timestamp: $(date -Iseconds)"

# Change to app directory and execute
cd /app
exec python "$@"