#!/bin/bash

# Start Generic Orchestrator with proper error handling
# This script creates a general-purpose orchestrator that can handle any PRP

echo "🚀 Starting Generic Orchestrator..."

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
tmux kill-session -t orchestrator 2>/dev/null || true

# Create new orchestrator session
echo "📋 Creating orchestrator session..."
tmux new-session -d -s orchestrator -c "/Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final"

# Check if session was created
if tmux has-session -t orchestrator 2>/dev/null; then
    echo "✅ Orchestrator session created successfully"
    echo ""
    echo "🎯 Next steps:"
    echo "1. Attach to the session:"
    echo "   tmux attach -t orchestrator"
    echo ""
    echo "2. Start Claude:"
    echo "   claude"
    echo ""
    echo "3. Give Claude the orchestrator briefing:"
    echo "   'You are the Orchestrator with exclusive authority over PRP state management."
    echo "   You can handle any PRP. Read ORCHESTRATOR_SETUP_GUIDE.md and ORCHESTRATOR_PRP_AUTHORITY.md"
    echo "   to understand your role. What PRP would you like to work on?'"
    echo ""
    echo "📊 Available PRPs:"
    python .claude/prp_tracking/cli_commands.py list 2>/dev/null || echo "Could not get PRP list"
    echo ""
    echo "🛠️ Available Commands:"
    echo "   - View PRP status: python .claude/prp_tracking/cli_commands.py status [PRP-ID]"
    echo "   - Orchestrator validation: python /Users/charlieirwin/Tmux-Orchestrator/orchestrator_prp_commands.py check [PRP-ID]"
    echo "   - Agent messaging: /Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh session:window 'message'"
    echo "   - Self-scheduling: /Users/charlieirwin/Tmux-Orchestrator/schedule_with_note.sh 15 'Check progress'"
else
    echo "❌ Failed to create orchestrator session"
    exit 1
fi