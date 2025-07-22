#!/usr/bin/env bash
# Redis-tmux bridge for validator agent
set -euo pipefail

QUEUE=${1:-validation_queue}
INFLIGHT=${QUEUE}:inflight
PANE_NAME=${2:-validator}
REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}

echo "Starting validator shim for queue: $QUEUE, pane: $PANE_NAME"

while true; do
    # Block until PRP appears in queue
    prp=$(redis-cli -u "$REDIS_URL" --raw BLPOP "$QUEUE" 0 | tail -n1)
    
    if [ -n "$prp" ]; then
        # Move to inflight queue
        redis-cli -u "$REDIS_URL" LPUSH "$INFLIGHT" "$prp"
        
        # Push to Claude pane
        tmux send-keys -t "leadstack:$PANE_NAME" "✅ PRP READY FOR VALIDATION: $prp

Please validate this completed PRP:
- Review code quality and standards
- Run tests and validation
- Check all acceptance criteria
- Mark as validated or send back for fixes

PRP ID: $prp"
        tmux send-keys -t "leadstack:$PANE_NAME" Enter
        
        echo "$(date): Sent PRP $prp to $PANE_NAME for validation"
    fi
done