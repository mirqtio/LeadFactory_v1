#!/bin/bash

echo "🔴 SHUTTING DOWN LEADSTACK MULTI-AGENT SYSTEM"

# Kill any running enterprise shims first
echo "1. Killing enterprise shims..."
pkill -f enterprise_shim 2>/dev/null || echo "   No enterprise shims running"

# Clean up PID file if it exists
rm -f /tmp/enterprise_shim_pids.txt

# Send exit commands to all Claude Code panes
echo "2. Sending exit commands to Claude panes..."
for pane in orchestrator dev-1 dev-2 validator integrator; do
    echo "   Exiting Claude in $pane..."
    tmux send-keys -t leadstack:$pane "exit" C-m 2>/dev/null || echo "   Pane $pane not found"
    sleep 1
done

# Kill the entire tmux session
echo "3. Killing tmux session 'leadstack'..."
tmux kill-session -t leadstack 2>/dev/null || echo "   Session 'leadstack' not found"

# Clear Redis state
echo "4. Clearing Redis state..."
redis-cli FLUSHALL 2>/dev/null || echo "   Redis not accessible"

# Clean up any log files
echo "5. Cleaning up log files..."
rm -f /tmp/enterprise_shim_*.log 2>/dev/null || true

echo "✅ SHUTDOWN COMPLETE"
echo ""
echo "System is ready for fresh restart with start_stack.sh"
echo "All agents terminated, tmux session killed, Redis cleared"