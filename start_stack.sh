#!/bin/bash
set -euo pipefail

# LeadFactory Multi-Agent Stack Startup Script
# One-command deployment of entire Redis-queue-based agent orchestration

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK_SESSION="leadstack"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log() { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

# Check dependencies
check_dependencies() {
    log "Checking system dependencies..."
    
    command -v tmux >/dev/null 2>&1 || error "tmux is required but not installed"
    command -v redis-cli >/dev/null 2>&1 || error "redis-cli is required but not installed"
    command -v claude >/dev/null 2>&1 || error "claude is required but not installed"
    
    success "All dependencies available"
}

# Load environment variables
load_environment() {
    log "Loading environment configuration..."
    
    if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
        error ".env file not found in ${SCRIPT_DIR}"
    fi
    
    set -a
    source "${SCRIPT_DIR}/.env"
    set +a
    
    # Validate required environment variables
    required_vars=(
        "REDIS_URL"
        "VPS_SSH_HOST"
        "VPS_SSH_USER"
        "VPS_SSH_KEY"
        "CLAUDE_ORCH_MODEL"
        "CLAUDE_DEV_MODEL"
    )
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            error "Required environment variable $var is not set"
        fi
    done
    
    success "Environment loaded successfully"
}

# Test Redis connectivity
test_redis() {
    log "Testing Redis connectivity..."
    
    if ! redis-cli -u "${REDIS_URL}" ping >/dev/null 2>&1; then
        error "Cannot connect to Redis at ${REDIS_URL}"
    fi
    
    success "Redis connection verified"
}

# Test SSH connectivity
test_ssh() {
    log "Testing SSH connectivity..."
    
    if [[ ! -f "${VPS_SSH_KEY}" ]]; then
        error "SSH key not found: ${VPS_SSH_KEY}"
    fi
    
    # Fix SSH key permissions
    chmod 600 "${VPS_SSH_KEY}"
    
    # Test SSH connection
    if ! ssh -i "${VPS_SSH_KEY}" -o ConnectTimeout=10 -o StrictHostKeyChecking=accept-new \
         "${VPS_SSH_USER}@${VPS_SSH_HOST}" "echo 'SSH OK'" >/dev/null 2>&1; then
        warn "SSH connection test failed - integrator may have issues"
    else
        success "SSH connection verified"
    fi
}

# Initialize Redis queues
init_redis_queues() {
    log "Initializing Redis queues..."
    
    local queues=("dev_queue" "validation_queue" "integration_queue" "orchestrator_queue" "completion_queue")
    
    for queue in "${queues[@]}"; do
        if ! redis-cli -u "${REDIS_URL}" EXISTS "$queue" >/dev/null 2>&1; then
            redis-cli -u "${REDIS_URL}" LPUSH "$queue" "__init__" >/dev/null
            redis-cli -u "${REDIS_URL}" LPOP "$queue" >/dev/null
            log "Initialized queue: $queue"
        fi
        
        # Initialize inflight queues
        redis-cli -u "${REDIS_URL}" EXISTS "${queue}:inflight" >/dev/null || \
            redis-cli -u "${REDIS_URL}" LPUSH "${queue}:inflight" "__init__" >/dev/null && \
            redis-cli -u "${REDIS_URL}" LPOP "${queue}:inflight" >/dev/null
    done
    
    # Initialize status tracking
    redis-cli -u "${REDIS_URL}" HSET "orchestrator:status" "started_at" "$(date -Iseconds)" >/dev/null
    redis-cli -u "${REDIS_URL}" HSET "orchestrator:status" "session" "${STACK_SESSION}" >/dev/null
    
    success "Redis queues initialized"
}

# Generate context injection payloads
generate_context() {
    log "Generating agent context payloads..."
    
    local claude_summary=""
    local project_summary=""
    
    # Extract CLAUDE.md summary
    if [[ -f "${SCRIPT_DIR}/CLAUDE.md" ]]; then
        claude_summary=$(head -20 "${SCRIPT_DIR}/CLAUDE.md" | sed 's/"/\\"/g')
    fi
    
    # Extract PROJECT_CONTEXT.md or generate basic summary
    if [[ -f "${SCRIPT_DIR}/PROJECT_CONTEXT.md" ]]; then
        project_summary=$(head -20 "${SCRIPT_DIR}/PROJECT_CONTEXT.md" | sed 's/"/\\"/g')
    else
        project_summary="LeadFactory Multi-Agent System - Redis Queue Orchestration"
    fi
    
    # Store context in temp files for injection
    cat > "/tmp/orch_context.txt" <<EOF
SYSTEM CONTEXT INJECTION:

ORGANIZATIONAL CONTEXT:
${claude_summary}

PROJECT CONTEXT:
${project_summary}

You are the orchestrator/architect agent responsible for:
- PRP workflow coordination
- Agent task assignment
- System health monitoring
- Strategic decision making

Your Redis queues: orchestrator_queue (incoming), dev_queue/validation_queue/integration_queue (outgoing)
Session: ${STACK_SESSION} | Environment: ${ENVIRONMENT:-development}
EOF

    cat > "/tmp/dev_context.txt" <<EOF
SYSTEM CONTEXT INJECTION:

ORGANIZATIONAL CONTEXT:
${claude_summary}

PROJECT CONTEXT:
${project_summary}

You are a development agent responsible for:
- PRP implementation
- Code development
- Technical implementation
- Feature creation

Your Redis queue: dev_queue
Session: ${STACK_SESSION} | Environment: ${ENVIRONMENT:-development}
EOF

    cat > "/tmp/validator_context.txt" <<EOF
SYSTEM CONTEXT INJECTION:

ORGANIZATIONAL CONTEXT:
${claude_summary}

PROJECT CONTEXT:
${project_summary}

You are a validation agent responsible for:
- Code review
- Quality assurance
- Testing validation
- Standards compliance

Your Redis queue: validation_queue
Session: ${STACK_SESSION} | Environment: ${ENVIRONMENT:-development}
EOF

    cat > "/tmp/integrator_context.txt" <<EOF
SYSTEM CONTEXT INJECTION:

ORGANIZATIONAL CONTEXT:
${claude_summary}

PROJECT CONTEXT:
${project_summary}

You are an integration agent responsible for:
- Deployment coordination
- VPS integration
- System integration
- Production deployment

Your Redis queue: integration_queue
SSH Access: ${VPS_SSH_USER}@${VPS_SSH_HOST}
Session: ${STACK_SESSION} | Environment: ${ENVIRONMENT:-development}
EOF

    success "Context payloads generated"
}

# Start enterprise shims for Redis-tmux coordination
start_enterprise_shims() {
    log "Starting enterprise shims for Redis-tmux coordination..."
    
    # Kill any existing shims first
    pkill -f enterprise_shim 2>/dev/null || true
    
    # Agent configurations: type, tmux_window, queue_name
    local agents=(
        "orchestrator:orchestrator:orchestrator_queue"
        "pm:dev-1:dev_queue" 
        "pm:dev-2:dev_queue"
        "validator:validator:validation_queue"
        "integrator:integrator:integration_queue"
    )
    
    # Start each enterprise shim
    for agent_config in "${agents[@]}"; do
        IFS=':' read -r agent_type tmux_window queue_name <<< "$agent_config"
        
        log "Starting $agent_type shim for $tmux_window (queue: $queue_name)"
        
        # Start enterprise shim in background
        python3 "${SCRIPT_DIR}/bin/enterprise_shim.py" \
            --agent-type="$agent_type" \
            --session="$STACK_SESSION" \
            --window="$tmux_window" \
            --queue="$queue_name" \
            --redis-url="$REDIS_URL" \
            > "/tmp/enterprise_shim_${agent_type}_${tmux_window}.log" 2>&1 &
        
        local shim_pid=$!
        log "Started $agent_type shim (PID: $shim_pid)"
        
        # Store PID for cleanup
        echo "$shim_pid" >> "/tmp/enterprise_shim_pids.txt"
        
        # Brief pause between shims
        sleep 1
    done
    
    # Wait for shims to initialize
    sleep 3
    
    # Verify shim processes
    local shim_count=$(ps aux | grep -c "enterprise_shim" | grep -v grep || echo 0)
    if [[ $shim_count -gt 0 ]]; then
        success "Enterprise shims started ($shim_count processes)"
    else
        error "Failed to start enterprise shims"
    fi
}

# Create or attach tmux session
setup_tmux_session() {
    log "Setting up tmux session: ${STACK_SESSION}"
    
    # Kill existing session if it exists
    if tmux has-session -t "${STACK_SESSION}" 2>/dev/null; then
        warn "Existing session found, killing..."
        tmux kill-session -t "${STACK_SESSION}"
    fi
    
    # Create new session with orchestrator window
    tmux new-session -d -s "${STACK_SESSION}" -n "orchestrator"
    
    # Create additional windows
    tmux new-window -t "${STACK_SESSION}" -n "dev-1"
    tmux new-window -t "${STACK_SESSION}" -n "dev-2"
    tmux new-window -t "${STACK_SESSION}" -n "validator"
    tmux new-window -t "${STACK_SESSION}" -n "integrator"
    tmux new-window -t "${STACK_SESSION}" -n "logs"
    
    success "Tmux session created"
}

# Start agent in specific window
start_agent() {
    local window="$1"
    local persona="$2"
    local model="$3"
    local context_file="$4"
    
    log "Starting $persona agent in window: $window"
    
    # Start claude with persona and skip permissions
    tmux send-keys -t "${STACK_SESSION}:${window}" \
        "claude --model=$model --dangerously-skip-permissions" Enter
    
    # Wait for Claude to start
    sleep 3
    
    # Inject context
    tmux send-keys -t "${STACK_SESSION}:${window}" \
        "$(cat "$context_file")" Enter
    
    # Send initial status update
    tmux send-keys -t "${STACK_SESSION}:${window}" \
        "Agent $persona ready. Session: ${STACK_SESSION}. Monitoring Redis queues..." Enter
}

# Setup monitoring dashboard
setup_monitoring() {
    log "Setting up monitoring dashboard..."
    
    # Create monitoring script
    cat > "/tmp/stack_monitor.sh" <<'EOF'
#!/bin/bash
while true; do
    clear
    echo "=== LeadFactory Stack Monitor ==="
    echo "Timestamp: $(date)"
    echo "Session: $TMUX_SESSION"
    echo ""
    
    echo "=== Queue Depths ==="
    echo "Dev Queue: $(redis-cli -u "$REDIS_URL" LLEN dev_queue 2>/dev/null || echo 'ERROR')"
    echo "Validation Queue: $(redis-cli -u "$REDIS_URL" LLEN validation_queue 2>/dev/null || echo 'ERROR')"
    echo "Integration Queue: $(redis-cli -u "$REDIS_URL" LLEN integration_queue 2>/dev/null || echo 'ERROR')"
    echo "Orchestrator Queue: $(redis-cli -u "$REDIS_URL" LLEN orchestrator_queue 2>/dev/null || echo 'ERROR')"
    echo ""
    
    echo "=== Inflight Counts ==="
    echo "Dev Inflight: $(redis-cli -u "$REDIS_URL" LLEN dev_queue:inflight 2>/dev/null || echo 'ERROR')"
    echo "Validation Inflight: $(redis-cli -u "$REDIS_URL" LLEN validation_queue:inflight 2>/dev/null || echo 'ERROR')"
    echo "Integration Inflight: $(redis-cli -u "$REDIS_URL" LLEN integration_queue:inflight 2>/dev/null || echo 'ERROR')"
    echo ""
    
    echo "=== System Status ==="
    redis-cli -u "$REDIS_URL" HGETALL orchestrator:status 2>/dev/null | \
    while IFS= read -r line; do
        echo "$line"
    done | paste - - | while IFS=$'\t' read -r key value; do
        echo "$key: $value"
    done
    echo ""
    
    echo "=== Agent Health ==="
    for window in orchestrator dev-1 dev-2 validator integrator; do
        if tmux list-windows -t "$TMUX_SESSION" | grep -q "$window"; then
            echo "✅ $window: active"
        else
            echo "❌ $window: missing"
        fi
    done
    echo ""
    
    echo "=== VPS Status ==="
    if command -v ssh >/dev/null 2>&1 && [[ -n "${VPS_SSH_KEY:-}" ]] && [[ -n "${VPS_SSH_HOST:-}" ]]; then
        if ssh -i "$VPS_SSH_KEY" -o ConnectTimeout=5 -o StrictHostKeyChecking=no \
               "${VPS_SSH_USER}@${VPS_SSH_HOST}" "uptime" 2>/dev/null; then
            echo "✅ VPS: connected"
        else
            echo "❌ VPS: unreachable"
        fi
    else
        echo "⚠️ VPS: not configured"
    fi
    
    sleep 30
done
EOF
    
    chmod +x "/tmp/stack_monitor.sh"
    
    # Start monitoring in logs window
    tmux send-keys -t "${STACK_SESSION}:logs" \
        "export TMUX_SESSION='${STACK_SESSION}' REDIS_URL='${REDIS_URL}' VPS_SSH_KEY='${VPS_SSH_KEY}' VPS_SSH_HOST='${VPS_SSH_HOST}' VPS_SSH_USER='${VPS_SSH_USER}'" Enter
    
    tmux send-keys -t "${STACK_SESSION}:logs" \
        "/tmp/stack_monitor.sh" Enter
}

# Ingest backlog PRPs
ingest_backlog() {
    if [[ "$1" == "--no-ingest" ]]; then
        log "Skipping backlog ingest as requested"
        return
    fi
    
    log "Checking for backlog PRPs..."
    
    if [[ -d "${SCRIPT_DIR}/backlog_prps" ]] && [[ -n "$(ls -A "${SCRIPT_DIR}/backlog_prps"/*.md 2>/dev/null)" ]]; then
        log "Found backlog PRPs, creating ingest script..."
        
        # Create PRP ingest script
        cat > "${SCRIPT_DIR}/scripts/prp_ingest.py" <<'EOF'
#!/usr/bin/env python3
"""
PRP Backlog Ingest Script
Scans backlog_prps/ directory and queues PRPs in Redis
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
import redis

def parse_prp_file(file_path):
    """Parse PRP markdown file for metadata."""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Extract front matter
    frontmatter_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL | re.MULTILINE)
    if not frontmatter_match:
        return None
    
    frontmatter = frontmatter_match.group(1)
    
    # Parse YAML-like front matter
    metadata = {}
    for line in frontmatter.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            metadata[key.strip()] = value.strip().strip('"\'')
    
    return metadata

def main():
    if len(sys.argv) < 2:
        print("Usage: python prp_ingest.py <backlog_directory>")
        sys.exit(1)
    
    backlog_dir = Path(sys.argv[1])
    if not backlog_dir.exists():
        print(f"Backlog directory not found: {backlog_dir}")
        sys.exit(1)
    
    # Connect to Redis
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    try:
        r = redis.from_url(redis_url)
        r.ping()
    except Exception as e:
        print(f"Redis connection failed: {e}")
        sys.exit(1)
    
    queued_count = 0
    
    # Process all markdown files
    for prp_file in backlog_dir.glob('*.md'):
        try:
            metadata = parse_prp_file(prp_file)
            if not metadata:
                print(f"⚠️ No metadata found in {prp_file.name}")
                continue
            
            prp_id = metadata.get('id', prp_file.stem)
            priority_stage = metadata.get('priority_stage', 'dev').lower()
            
            # Map stage to queue
            queue_map = {
                'dev': 'dev_queue',
                'development': 'dev_queue',
                'validation': 'validation_queue',
                'integration': 'integration_queue',
                'orchestrator': 'orchestrator_queue'
            }
            
            target_queue = queue_map.get(priority_stage, 'dev_queue')
            
            # Create PRP hash
            prp_key = f"prp:{prp_id}"
            prp_data = {
                'id': prp_id,
                'title': metadata.get('title', prp_file.stem),
                'description': metadata.get('description', ''),
                'priority_stage': priority_stage,
                'status': 'queued',
                'retry_count': '0',
                'added_at': datetime.utcnow().isoformat(),
                'source_file': str(prp_file),
                'content': prp_file.read_text()
            }
            
            # Store in Redis
            r.hset(prp_key, mapping=prp_data)
            r.lpush(target_queue, prp_id)
            
            print(f"✅ Queued {prp_id} → {target_queue}")
            queued_count += 1
            
        except Exception as e:
            print(f"❌ Failed to process {prp_file.name}: {e}")
    
    print(f"\n📊 Ingest complete: {queued_count} PRPs queued")
    
    # Broadcast completion
    broadcast_msg = json.dumps({
        'type': 'system_broadcast',
        'message': f'Backlog ingest complete, {queued_count} PRPs queued.',
        'timestamp': datetime.utcnow().isoformat()
    })
    r.lpush('orchestrator_queue', broadcast_msg)

if __name__ == '__main__':
    main()
EOF
        
        chmod +x "${SCRIPT_DIR}/scripts/prp_ingest.py"
        
        # Run ingest
        python3 "${SCRIPT_DIR}/scripts/prp_ingest.py" "${SCRIPT_DIR}/backlog_prps"
        success "Backlog ingest completed"
    else
        log "No backlog PRPs found, skipping ingest"
    fi
}

# Main execution
main() {
    local no_ingest=""
    if [[ "$1" == "--no-ingest" ]]; then
        no_ingest="--no-ingest"
    fi
    
    log "Starting LeadFactory Multi-Agent Stack..."
    
    # Pre-flight checks
    check_dependencies
    load_environment
    test_redis
    test_ssh
    
    # Redis setup
    init_redis_queues
    
    # Context preparation
    generate_context
    
    # Tmux session setup
    setup_tmux_session
    
    # Start agents
    start_agent "orchestrator" "orchestrator" "${CLAUDE_ORCH_MODEL}" "/tmp/orch_context.txt"
    start_agent "dev-1" "dev" "${CLAUDE_DEV_MODEL}" "/tmp/dev_context.txt"
    start_agent "dev-2" "dev" "${CLAUDE_DEV_MODEL}" "/tmp/dev_context.txt"
    start_agent "validator" "validator" "${CLAUDE_DEV_MODEL}" "/tmp/validator_context.txt"
    start_agent "integrator" "integrator" "${CLAUDE_DEV_MODEL}" "/tmp/integrator_context.txt"
    
    # Setup monitoring
    setup_monitoring
    
    # Start enterprise shims
    start_enterprise_shims
    
    # Ingest backlog
    ingest_backlog "$no_ingest"
    
    # Final status
    success "Stack deployment complete!"
    log "Tmux session: ${STACK_SESSION}"
    log "Attach with: tmux attach-session -t ${STACK_SESSION}"
    log "Monitor logs in 'logs' window"
    log "Use Ctrl+b then window number to switch between agents"
    
    # Auto-attach to session
    exec tmux attach-session -t "${STACK_SESSION}"
}

# Run with error handling
trap 'error "Script failed at line $LINENO"' ERR

# Check if running directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "${1:-}"
fi