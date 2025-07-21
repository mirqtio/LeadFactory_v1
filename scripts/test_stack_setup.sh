#!/bin/bash
# Test script for LeadFactory stack prerequisites

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[TEST]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[FAIL]${NC} $1"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

test_count=0
pass_count=0

run_test() {
    local test_name="$1"
    local test_command="$2"
    
    ((test_count++))
    echo -n "Testing $test_name... "
    
    if eval "$test_command" >/dev/null 2>&1; then
        echo -e "${GREEN}PASS${NC}"
        ((pass_count++))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        return 1
    fi
}

log "LeadFactory Stack Prerequisites Test"
echo "=================================="

# Test dependencies
run_test "tmux installation" "command -v tmux"
run_test "redis-cli installation" "command -v redis-cli"
run_test "python3 installation" "command -v python3"
run_test "claude-code installation" "command -v claude-code"

# Test project structure
run_test "project root exists" "test -d '$PROJECT_ROOT'"
run_test ".env file exists" "test -f '$PROJECT_ROOT/.env'"
run_test "start_stack.sh exists" "test -f '$PROJECT_ROOT/start_stack.sh'"
run_test "start_stack.sh executable" "test -x '$PROJECT_ROOT/start_stack.sh'"

# Test .env configuration
if [[ -f "$PROJECT_ROOT/.env" ]]; then
    source "$PROJECT_ROOT/.env"
    
    run_test "REDIS_URL configured" "test -n '${REDIS_URL:-}'"
    run_test "VPS_SSH_HOST configured" "test -n '${VPS_SSH_HOST:-}'"
    run_test "VPS_SSH_USER configured" "test -n '${VPS_SSH_USER:-}'"
    run_test "VPS_SSH_KEY configured" "test -n '${VPS_SSH_KEY:-}'"
    run_test "CLAUDE_ORCH_MODEL configured" "test -n '${CLAUDE_ORCH_MODEL:-}'"
    run_test "CLAUDE_DEV_MODEL configured" "test -n '${CLAUDE_DEV_MODEL:-}'"
    
    # Test SSH key
    if [[ -n "${VPS_SSH_KEY:-}" ]]; then
        run_test "SSH key file exists" "test -f '$VPS_SSH_KEY'"
        if [[ -f "$VPS_SSH_KEY" ]]; then
            run_test "SSH key permissions" "test '$(stat -f %Mp%Lp '$VPS_SSH_KEY' 2>/dev/null || stat -c %a '$VPS_SSH_KEY' 2>/dev/null)' = '600'"
        fi
    fi
    
    # Test Redis connectivity
    if [[ -n "${REDIS_URL:-}" ]]; then
        run_test "Redis connectivity" "redis-cli -u '$REDIS_URL' ping"
    fi
    
    # Test SSH connectivity (non-blocking)
    if [[ -n "${VPS_SSH_HOST:-}" ]] && [[ -n "${VPS_SSH_USER:-}" ]] && [[ -n "${VPS_SSH_KEY:-}" ]] && [[ -f "${VPS_SSH_KEY:-}" ]]; then
        echo -n "Testing SSH connectivity (may take 10s)... "
        if timeout 10 ssh -i "$VPS_SSH_KEY" -o ConnectTimeout=10 -o StrictHostKeyChecking=no \
           "$VPS_SSH_USER@$VPS_SSH_HOST" "echo 'SSH OK'" >/dev/null 2>&1; then
            echo -e "${GREEN}PASS${NC}"
            ((pass_count++))
        else
            echo -e "${YELLOW}WARN${NC} (SSH may still work during deployment)"
        fi
        ((test_count++))
    fi
fi

# Test Python modules
run_test "redis-py module" "python3 -c 'import redis'"
run_test "yaml module" "python3 -c 'import yaml'"

echo
echo "=================================="
echo "Test Results: $pass_count/$test_count passed"

if [[ $pass_count -eq $test_count ]]; then
    log "All tests passed! Stack is ready to deploy."
    echo
    echo "Next steps:"
    echo "1. Run: ./start_stack.sh"
    echo "2. Or: ./start_stack.sh --no-ingest"
    exit 0
else
    error "Some tests failed. Please address issues before running stack."
    echo
    echo "Common fixes:"
    echo "- Install missing dependencies with brew/apt"
    echo "- Configure .env file variables"
    echo "- Fix SSH key permissions: chmod 600 ~/.ssh/your_key"
    echo "- Start Redis server: redis-server"
    exit 1
fi