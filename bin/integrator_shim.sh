#!/usr/bin/env bash
# Redis-tmux bridge for integrator agent
set -euo pipefail

QUEUE=${1:-integration_queue}
INFLIGHT=${QUEUE}:inflight
PANE_NAME=${2:-integrator}
REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}

echo "Starting integrator shim for queue: $QUEUE, pane: $PANE_NAME"

while true; do
    # Block until PRP appears in queue
    prp=$(redis-cli -u "$REDIS_URL" --raw BLPOP "$QUEUE" 0 | tail -n1)
    
    if [ -n "$prp" ]; then
        # Move to inflight queue
        redis-cli -u "$REDIS_URL" LPUSH "$INFLIGHT" "$prp"
        
        # Push to Claude pane
        tmux send-keys -t "leadstack:$PANE_NAME" "🚀 PRP READY FOR INTEGRATION: $prp

Please integrate this validated PRP:
- Merge to main branch
- Deploy to VPS
- Run integration tests
- Monitor deployment health

SSH Access: \$VPS_SSH_USER@\$VPS_SSH_HOST
PRP ID: $prp"
        tmux send-keys -t "leadstack:$PANE_NAME" Enter
        
        echo "$(date): Sent PRP $prp to $PANE_NAME for integration"
    fi
done