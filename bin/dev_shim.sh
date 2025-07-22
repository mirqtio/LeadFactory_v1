#!/usr/bin/env bash
# Redis-tmux bridge for dev agents
set -euo pipefail

QUEUE=${1:-dev_queue}
INFLIGHT=${QUEUE}:inflight
PANE_NAME=${2:-dev-1}
REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}

echo "Starting dev shim for queue: $QUEUE, pane: $PANE_NAME"

while true; do
    # Block until PRP appears in queue
    prp=$(redis-cli -u "$REDIS_URL" --raw BLPOP "$QUEUE" 0 | tail -n1)
    
    if [ -n "$prp" ]; then
        # Move to inflight queue
        redis-cli -u "$REDIS_URL" LPUSH "$INFLIGHT" "$prp"
        
        # Push to Claude pane
        tmux send-keys -t "leadstack:$PANE_NAME" "🔥 NEW PRP ASSIGNED: $prp

Please implement this PRP following CLAUDE.md guidelines.
- Read the PRP file for requirements
- Follow validation steps
- Ask questions if blocked
- Mark complete when finished

PRP ID: $prp"
        tmux send-keys -t "leadstack:$PANE_NAME" Enter
        
        echo "$(date): Sent PRP $prp to $PANE_NAME"
    fi
done