#!/bin/bash
while true; do
    echo "=== ORCHESTRATOR ACTIVE COORDINATION CYCLE Thu Jul 17 23:01:43 EDT 2025 ==="
    
    # Send agent checkins
    /Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh orchestrator:1 "Scheduled checkin: Progress report on Core API/Gateway coverage. Current status and next 30min goals?"
    /Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh orchestrator:3 "Scheduled checkin: Progress report on Business Logic coverage. Current status and next 30min goals?"
    /Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh orchestrator:4 "Scheduled checkin: Progress report on Data/Infrastructure coverage. Current status and next 30min goals?"
    
    # UPDATE DASHBOARD
    python update_status.py
    
    # PROMPT ORCHESTRATOR TO TAKE ACTION
    echo ""
    echo "🚨 ORCHESTRATOR ACTION REQUIRED 🚨"
    echo "Check agent responses and take immediate action:"
    echo "1. Review agent progress reports"
    echo "2. Remove any blockers"
    echo "3. Reassign work if needed"
    echo "4. Provide specific guidance"
    echo "5. Update PRP status if tasks complete"
    echo ""
    echo "CRITICAL: Do not mark coordination tasks complete until results achieved!"
    echo ""
    
    # Wait for next cycle
    echo "Next coordination cycle in 30 minutes..."
    sleep 1800  # 30 minutes
done
