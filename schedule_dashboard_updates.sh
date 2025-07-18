#!/bin/bash

# Schedule recurring dashboard updates using the proper orchestrator mechanism
CURRENT_WINDOW=$(tmux display-message -p "#{session_name}:#{window_index}")

# Schedule the next update
/Users/charlieirwin/Tmux-Orchestrator/schedule_with_note.sh 2 "python3 update_status.py && /Users/charlieirwin/Documents/GitHub/LeadFactory_v1_Final/schedule_dashboard_updates.sh" "$CURRENT_WINDOW"