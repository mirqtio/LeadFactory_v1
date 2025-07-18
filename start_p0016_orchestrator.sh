#!/bin/bash

# Start P0-016 Orchestrator with proper error handling
# This script ensures tmux is available and starts the orchestrator correctly

echo "🚀 Starting P0-016 Orchestrator..."

# Check if tmux is available
if ! command -v tmux &> /dev/null; then
    echo "❌ tmux not found. Installing..."
    brew install tmux
fi

# Check if in correct directory
if [ ! -f ".claude/prp_tracking/prp_status.yaml" ]; then
    echo "❌ Must be run from LeadFactory_v1_Final directory"
    echo "Run: cd /Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final"
    exit 1
fi

# Kill existing orchestrator session if it exists
tmux kill-session -t p0016-orchestrator 2>/dev/null || true

# Create new orchestrator session
echo "📋 Creating orchestrator session..."
tmux new-session -d -s p0016-orchestrator -c "/Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final"

# Check if session was created
if tmux has-session -t p0016-orchestrator 2>/dev/null; then
    echo "✅ Orchestrator session created successfully"
    echo ""
    echo "🎯 Next steps:"
    echo "1. Attach to the session:"
    echo "   tmux attach -t p0016-orchestrator"
    echo ""
    echo "2. Start Claude:"
    echo "   claude"
    echo ""
    echo "3. Give Claude the orchestrator briefing:"
    echo "   'You are the P0-016 orchestrator with exclusive authority over PRP state management."
    echo "   Read ORCHESTRATOR_SETUP_GUIDE.md and begin coordinating P0-016 completion.'"
    echo ""
    echo "📊 Current P0-016 Status:"
    python .claude/prp_tracking/cli_commands.py status P0-016 2>/dev/null || echo "Could not get PRP status"
else
    echo "❌ Failed to create orchestrator session"
    exit 1
fi