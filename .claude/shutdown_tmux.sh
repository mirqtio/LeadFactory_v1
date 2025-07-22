#!/bin/bash
# Graceful tmux orchestration shutdown script
# Properly terminates all PM sessions, agents, and orchestrator

echo "🔄 GRACEFUL TMUX ORCHESTRATION SHUTDOWN"
echo "======================================"

# Function to send graceful shutdown to a tmux session
shutdown_session() {
    local session_name="$1"
    echo "📤 Sending shutdown signal to $session_name..."
    
    # Send Ctrl+C to interrupt any running processes
    tmux send-keys -t "$session_name" C-c 2>/dev/null || true
    sleep 0.5
    
    # Send exit command to close shells gracefully
    tmux send-keys -t "$session_name" "exit" Enter 2>/dev/null || true
    sleep 0.5
}

# Function to kill tmux session if graceful shutdown fails
force_kill_session() {
    local session_name="$1"
    echo "⚡ Force killing session: $session_name"
    tmux kill-session -t "$session_name" 2>/dev/null || true
}

# Check if tmux is running
if ! tmux list-sessions >/dev/null 2>&1; then
    echo "✅ No tmux sessions found - already clean"
    exit 0
fi

echo "📋 Current tmux sessions:"
tmux list-sessions

echo
echo "🛑 Starting graceful shutdown sequence..."

# Step 1: Stop any automation scripts first
echo "🔄 Stopping automation scripts..."
pkill -f "active_orchestration.sh" 2>/dev/null || true
pkill -f "schedule_with_note.sh" 2>/dev/null || true
pkill -f "auto_checkin.sh" 2>/dev/null || true
pkill -f "update_redis_dashboard.sh" 2>/dev/null || true
pkill -f "auto_update_status.sh" 2>/dev/null || true

# Step 2: Gracefully shutdown PM agent sessions
PM_SESSIONS=("PM-1" "PM-2" "PM-3")
for session in "${PM_SESSIONS[@]}"; do
    if tmux has-session -t "$session" 2>/dev/null; then
        shutdown_session "$session"
    fi
done

# Step 3: Shutdown supporting agent sessions
AGENT_SESSIONS=("validator" "integrator")
for session in "${AGENT_SESSIONS[@]}"; do
    if tmux has-session -t "$session" 2>/dev/null; then
        shutdown_session "$session"
    fi
done

echo "⏳ Waiting 3 seconds for graceful shutdowns..."
sleep 3

# Step 4: Shutdown orchestrator session (coordinator)
if tmux has-session -t "orchestrator" 2>/dev/null; then
    echo "📤 Shutting down orchestrator session..."
    
    # Send shutdown to each orchestrator window
    for window in 0 1 2 3 4 5; do
        tmux send-keys -t "orchestrator:$window" C-c 2>/dev/null || true
        sleep 0.2
        tmux send-keys -t "orchestrator:$window" "exit" Enter 2>/dev/null || true
    done
    
    sleep 2
fi

echo "⏳ Waiting 5 seconds for all processes to terminate..."
sleep 5

# Step 5: Force kill any remaining sessions
echo "🧹 Cleaning up any remaining sessions..."
ALL_SESSIONS=("PM-1" "PM-2" "PM-3" "validator" "integrator" "orchestrator")
for session in "${ALL_SESSIONS[@]}"; do
    if tmux has-session -t "$session" 2>/dev/null; then
        force_kill_session "$session"
    fi
done

# Step 6: Kill any remaining Node.js processes (task-master-ai)
echo "🔄 Cleaning up Node.js processes..."
pkill -f "task-master-ai" 2>/dev/null || true
pkill -f "node.*pm" 2>/dev/null || true

# Step 7: Final verification
echo
echo "🔍 Final verification..."
if tmux list-sessions >/dev/null 2>&1; then
    echo "⚠️  Some tmux sessions still running:"
    tmux list-sessions
    echo
    echo "💥 Force killing all remaining tmux sessions..."
    tmux kill-server
else
    echo "✅ All tmux sessions successfully terminated"
fi

echo
echo "🧹 Cleanup complete!"
echo "📋 System Status:"
echo "  ✅ Automation scripts stopped"
echo "  ✅ PM agent sessions terminated"  
echo "  ✅ Support agent sessions terminated"
echo "  ✅ Orchestrator session terminated"
echo "  ✅ Node.js processes cleaned"
echo "  ✅ Tmux server clean"
echo
echo "🚀 Ready for fresh tmux session startup"
echo "   You can now run your tmux initialization script cleanly"