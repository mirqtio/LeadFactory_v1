#!/bin/bash
while true; do
    echo "=== ORCHESTRATOR SCHEDULED CHECKIN Thu Jul 17 21:35:35 EDT 2025 ==="
    /Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh orchestrator:1 "Scheduled checkin: Progress report on Core API/Gateway coverage. Current status and next 30min goals?"
    /Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh orchestrator:3 "Scheduled checkin: Progress report on Business Logic coverage. Current status and next 30min goals?"
    /Users/charlieirwin/Tmux-Orchestrator/send-claude-message.sh orchestrator:4 "Scheduled checkin: Progress report on Data/Infrastructure coverage. Current status and next 30min goals?"
    python update_status.py
    echo "Next checkin in 30 minutes..."
    sleep 1800  # 30 minutes
done
