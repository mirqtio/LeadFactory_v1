#!/usr/bin/env bash
# Redis-tmux bridge for orchestrator agent
set -euo pipefail

QUEUE=${1:-orchestrator_queue}
INFLIGHT=${QUEUE}:inflight
PANE_NAME=${2:-orchestrator}
REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}

echo "Starting orchestrator shim for queue: $QUEUE, pane: $PANE_NAME"

while true; do
    # Block until message appears in queue
    message=$(redis-cli --raw BLPOP "$QUEUE" 0 | tail -n1)
    
    if [ -n "$message" ]; then
        # Move to inflight queue
        redis-cli LPUSH "$INFLIGHT" "$message"
        
        # Push to Claude pane
        tmux send-keys -t "leadstack:$PANE_NAME" "🎯 ORCHESTRATOR COMMAND: $message

Please process this orchestration command:
- Analyze the request
- Assign work to appropriate queues (dev_queue, validation_queue, integration_queue)
- Update Redis state as needed
- Monitor progress

Use Redis commands to manage queues:
- Add to dev queue: redis-cli LPUSH dev_queue \"PRP-ID\"
- Check queue status: redis-cli LLEN queue_name
- View queue contents: redis-cli LRANGE queue_name 0 -1

Command: $message"
        tmux send-keys -t "leadstack:$PANE_NAME" Enter
        
        echo "$(date): Sent orchestrator command $message to $PANE_NAME"
    fi
done